#!/usr/bin/env python3
"""Read-only checks for explicit rig contracts and observed motion traces."""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('expected a finite number')
    return float(value)


def vector(value, size=2):
    if not isinstance(value, list) or len(value) != size:
        raise ValueError(f'expected a {size}-component vector')
    return [number(v) for v in value]


def identifier(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('expected a nonempty identifier')
    return value


def unique(items, label):
    values = [identifier(item['id']) for item in items]
    if len(values) != len(set(values)):
        raise ValueError(f'duplicate {label} ids')
    return values


def result(errors, metrics, coverage):
    return {'ok': not errors, 'errors': errors, 'metrics': metrics, 'coverage': coverage}


def audit_rig(data):
    if data['schema_version'] != 1:
        raise ValueError('unsupported schema_version')
    coords = data['coordinate_system']
    for field in ('origin', 'units', 'x_axis', 'y_axis', 'positive_rotation', 'bone_zero_axis'):
        identifier(coords[field])
    if coords['side_naming'] != 'anatomical':
        raise ValueError('export must declare anatomical side naming; adapt legacy screen names first')
    if coords['x_axis'] != 'right' or coords['y_axis'] not in ('up', 'down'):
        raise ValueError('unsupported axes; normalize export to X-right and Y-up/down')
    expected_rotation = 'clockwise' if coords['y_axis'] == 'down' else 'counterclockwise'
    if coords['positive_rotation'] != expected_rotation or coords['bone_zero_axis'] not in ('+x', '+y', '-x', '-y'):
        raise ValueError('inconsistent standard rotation/zero-axis declaration')
    view = data['view']
    if view not in ('front', 'back', 'three-quarter', 'profile') or not isinstance(data['mirrored'], bool):
        raise ValueError('invalid view or mirrored flag')
    tolerance = number(data['length_tolerance'])
    if tolerance < 0:
        raise ValueError('length_tolerance must be nonnegative')
    bones, attachments = data['bones'], data['attachments']
    if not bones or not attachments:
        raise ValueError('rig needs bones and attachments')
    bone_ids = unique(bones, 'bone')
    attachment_ids = unique(attachments, 'attachment')
    lookup = dict(zip(bone_ids, bones))
    errors = []
    seen = set()
    roots = 0
    mapped_sides = 0
    for bone in bones:
        bid = bone['id']
        parent = bone['parent']
        length = number(bone['length'])
        if length < 0:
            raise ValueError('bone length must be nonnegative')
        offset = vector(bone['offset'])
        if parent is None:
            roots += 1
        elif parent not in seen:
            errors.append(f'{bid}: parent must exist before child (cycle or invalid ordering)')
        elif bone.get('attachment_point') == 'parent-distal':
            axis = coords['bone_zero_axis']
            direction = {'+x': [1,0], '-x': [-1,0], '+y': [0,1], '-y': [0,-1]}[axis]
            expected = [n * number(lookup[parent]['length']) for n in direction]
            if math.dist(offset, expected) > tolerance:
                errors.append(f'{bid}: joint offset does not meet parent distal endpoint')
        if 'anatomical_side' in bone:
            side = bone['anatomical_side']
            screen = bone['screen_side_at_rest']
            if side not in ('left','right') or screen not in ('left','right'):
                raise ValueError('invalid side metadata')
            if view in ('front','back'):
                expected = ('right' if side == 'left' else 'left') if view == 'front' else side
                if data['mirrored']:
                    expected = 'right' if expected == 'left' else 'left'
                if screen != expected:
                    errors.append(f'{bid}: anatomical/screen side mismatch')
                mapped_sides += 1
        seen.add(bid)
    if roots != 1:
        errors.append('rig must have exactly one root')
    for part in attachments:
        aid = part['id']
        if part['bone'] not in lookup:
            errors.append(f'{aid}: unknown attachment bone')
            continue
        size = vector(part['size_px'])
        proximal, distal = vector(part['proximal_px']), vector(part['distal_px'])
        scale = number(part['scale'])
        if min(size) <= 0 or scale <= 0:
            raise ValueError('attachment size and uniform scale must be positive')
        for point in (proximal, distal):
            if not all(0 <= point[i] <= size[i] for i in range(2)):
                errors.append(f'{aid}: joint landmark is outside crop')
        source_length = math.dist(proximal, distal)
        target_length = number(lookup[part['bone']]['length'])
        if source_length <= 0 or target_length <= 0:
            errors.append(f'{aid}: zero-length segment')
        elif abs(source_length * scale - target_length) > tolerance:
            errors.append(f'{aid}: calibrated art length differs from bone length')
    order = data['draw_order']
    if not isinstance(order,list) or len(order) != len(set(order)) or set(order) != set(attachment_ids):
        errors.append('draw_order must contain every attachment exactly once')
    return result(errors, {'bones':len(bones),'attachments':len(attachments)},
                  {'mapped_side_bones':mapped_sides,'visual_anatomy':False,'visual_occlusion':False,'source_alpha':False})


def percentile(values, p):
    return sorted(values)[max(0, math.ceil(len(values) * p) - 1)]


def audit_trace(data):
    if data['schema_version'] != 1 or data['units'] != {'time':'ms','position':'css-px'}:
        raise ValueError('unsupported trace version or units')
    budget_names = ('max_frame_ms','p95_frame_ms','max_speed_px_per_second','position_slack_px',
                    'max_joint_speed_deg_per_second','angle_slack_deg','scale_tolerance','opacity_tolerance','foot_drift_px','grip_drift_px','matrix_tolerance')
    budget = {key:number(data['budgets'][key]) for key in budget_names}
    if any(value < 0 for value in budget.values()):
        raise ValueError('budgets must be nonnegative')
    samples = data['samples']
    if not isinstance(samples,list) or len(samples) < 2:
        raise ValueError('trace needs at least two real samples')
    required = data['required_actors']
    if not isinstance(required,list) or len(set(required)) != len(required):
        raise ValueError('invalid required_actors')
    required = set(identifier(v) for v in required)
    errors, gaps, previous, contacts = [], [], {}, {}
    coverage = {'foot_contacts':0,'grips':0,'joint_angles':0,'rigid_matrices':0,
                'visual_anatomy':False,'visual_occlusion':False,'physical_device':False}
    max_drift = max_grip = max_speed = max_joint_speed = 0.0
    joint_history = {}
    previous_time = None
    for sample in samples:
        time = number(sample['t_ms'])
        if previous_time is not None:
            dt = time - previous_time
            if dt <= 0:
                raise ValueError('timestamps must strictly increase')
            gaps.append(dt)
        actors = sample['actors']
        ids = set(unique(actors, 'actor within frame'))
        for aid in sorted(required - ids):
            errors.append(f'{time:g}ms {aid}: required actor missing')
        for actor in actors:
            aid, node = identifier(actor['id']), identifier(actor['node'])
            position, scale = vector(actor['root']), vector(actor['scale'])
            opacity = number(actor['opacity'])
            if not isinstance(actor['visible'],bool):
                raise ValueError('visible must be boolean')
            if aid in required and not actor['visible']:
                errors.append(f'{time:g}ms {aid}: required drawing node hidden')
            if any(abs(value-1) > budget['scale_tolerance'] for value in scale):
                errors.append(f'{time:g}ms {aid}: cumulative scale changed from approved scale')
            if abs(opacity-1) > budget['opacity_tolerance']:
                errors.append(f'{time:g}ms {aid}: cumulative opacity changed')
            if aid in previous:
                old = previous[aid]
                if old['node'] != node:
                    errors.append(f'{time:g}ms {aid}: rendering entity replaced')
                elapsed = (time-old['time'])/1000
                distance = math.dist(position, old['position'])
                speed = distance/elapsed
                max_speed = max(max_speed,speed)
                if distance > budget['max_speed_px_per_second']*elapsed + budget['position_slack_px']:
                    errors.append(f'{time:g}ms {aid}: position jump exceeds path budget')
            previous[aid] = {'node':node,'time':time,'position':position}
            feet = actor.get('feet',[])
            unique(feet,'foot')
            for foot in feet:
                point = vector(foot['world'])
                if not isinstance(foot['stance'],bool):
                    raise ValueError('stance must be boolean')
                if foot['stance']:
                    token = identifier(foot['contact'])
                    key = (aid,foot['id'],token)
                    anchor = contacts.setdefault(key,point)
                    drift = math.dist(point,anchor)
                    max_drift = max(max_drift,drift)
                    coverage['foot_contacts'] += 1
                    if drift > budget['foot_drift_px']:
                        errors.append(f'{time:g}ms {aid}/{foot["id"]}: planted foot drift')
            grips = actor.get('grips',[])
            unique(grips,'grip')
            for grip in grips:
                drift = math.dist(vector(grip['hand']),vector(grip['prop']))
                max_grip = max(max_grip,drift)
                coverage['grips'] += 1
                if drift > budget['grip_drift_px']:
                    errors.append(f'{time:g}ms {aid}/{grip["id"]}: grip detached')
            joints = actor.get('joints',[])
            unique(joints,'joint')
            for joint in joints:
                angle, lower, upper = (number(joint[k]) for k in ('angle_deg','min_deg','max_deg'))
                if lower > upper:
                    raise ValueError('invalid joint limits')
                if not lower <= angle <= upper:
                    errors.append(f'{time:g}ms {aid}/{joint["id"]}: joint limit exceeded')
                if 'bend_sign' in joint:
                    sign = number(joint['bend_sign'])
                    if sign not in (-1,1):
                        raise ValueError('bend_sign must be -1 or 1')
                    if angle*sign < -1e-6:
                        errors.append(f'{time:g}ms {aid}/{joint["id"]}: bend branch flipped')
                key = (aid, joint['id'])
                if key in joint_history:
                    old_time, old_angle = joint_history[key]
                    elapsed = (time-old_time)/1000
                    change = abs((angle-old_angle+180)%360-180)
                    max_joint_speed = max(max_joint_speed,change/elapsed)
                    if change > budget['max_joint_speed_deg_per_second']*elapsed + budget['angle_slack_deg']:
                        errors.append(f'{time:g}ms {aid}/{joint["id"]}: angular jump exceeds pose budget')
                joint_history[key] = (time, angle)
                coverage['joint_angles'] += 1
            matrices = actor.get('rigid_matrices',[])
            unique(matrices,'matrix')
            for matrix in matrices:
                a,b,c,d,_,_ = vector(matrix['world'],6)
                values = (abs(math.hypot(a,b)-1),abs(math.hypot(c,d)-1),abs(a*c+b*d),abs(abs(a*d-b*c)-1))
                if max(values) > budget['matrix_tolerance']:
                    errors.append(f'{time:g}ms {aid}/{matrix["id"]}: non-rigid matrix (scale/shear)')
                coverage['rigid_matrices'] += 1
        previous_time = time
    if not previous:
        raise ValueError('trace contains no actor observations')
    p95, longest = percentile(gaps,0.95), max(gaps)
    if p95 > budget['p95_frame_ms']:
        errors.append('p95 frame interval exceeds declared budget')
    if longest > budget['max_frame_ms']:
        errors.append('maximum frame interval exceeds declared budget')
    return result(errors, {'samples':len(samples),'intervals':len(gaps),'p50_ms':percentile(gaps,0.5),
                          'p95_ms':p95,'p99_ms':percentile(gaps,0.99),'max_ms':longest,
                          'over_50_ms':sum(v>50 for v in gaps),'max_foot_drift_px':max_drift,
                          'max_grip_drift_px':max_grip,'max_root_speed_px_per_second':max_speed,'max_joint_speed_deg_per_second':max_joint_speed},coverage)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kind',choices=['rig','trace'])
    parser.add_argument('input',type=Path)
    args = parser.parse_args()
    try:
        data = json.loads(args.input.read_text())
        report = (audit_rig if args.kind == 'rig' else audit_trace)(data)
    except (OSError,ValueError,KeyError,TypeError,IndexError,OverflowError) as error:
        print(json.dumps({'ok':False,'input_error':str(error)},ensure_ascii=False))
        return 2
    print(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False))
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
