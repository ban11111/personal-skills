import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]

def module(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/f'{name}.py')
    value=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value

validator=module('validate_repo')
installer=module('install_skill')


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'personal-skills'
        shutil.copytree(ROOT,self.root,ignore=shutil.ignore_patterns('.git','.venv','__pycache__'))

    def test_repository_validates(self):
        self.assertEqual(validator.validate(self.root),[])

    def test_unregistered_skill_rejected(self):
        (self.root/'catalog.json').write_text(json.dumps({'schemaVersion':1,'skills':[]}))
        self.assertTrue(validator.validate(self.root))

    def test_cross_skill_link_rejected(self):
        path=self.root/'skills/2d-character-animation/SKILL.md'
        path.write_text(path.read_text()+'\n[nonportable](../../README.md)\n')
        self.assertTrue(any('nonportable link' in e for e in validator.validate(self.root)))

    def test_personal_path_detected(self):
        (self.root/'oops.txt').write_text('/'+'Users'+'/sample/project/file')
        self.assertTrue(any('filesystem path' in e for e in validator.validate(self.root)))

    def test_link_install_is_idempotent_and_preserves_source(self):
        target=Path(self.temp.name)/'installed'
        path,state=installer.install('2d-character-animation',target,root=self.root)
        self.assertEqual(state,'linked')
        self.assertTrue(path.is_symlink())
        self.assertTrue((path/'SKILL.md').is_file())
        self.assertEqual(installer.install('2d-character-animation',target,root=self.root)[1],'already linked')

    def test_existing_directory_not_overwritten(self):
        target=Path(self.temp.name)/'installed'
        path=target/'2d-character-animation'
        path.mkdir(parents=True)
        marker=path/'user-file.txt'
        marker.write_text('preserve')
        with self.assertRaises(FileExistsError):
            installer.install('2d-character-animation',target,root=self.root)
        self.assertEqual(marker.read_text(),'preserve')

    def test_copy_and_traversal(self):
        target=Path(self.temp.name)/'installed'
        path,state=installer.install('2d-character-animation',target,copy=True,root=self.root)
        self.assertEqual(state,'copied')
        self.assertFalse(path.is_symlink())
        self.assertTrue((path/'SKILL.md').is_file())
        with self.assertRaises(ValueError):installer.install('../outside',target,root=self.root)


if __name__=='__main__':unittest.main()
