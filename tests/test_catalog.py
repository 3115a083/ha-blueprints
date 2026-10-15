"""Guard import URLs and the source metadata required by Blueprints Updater."""
from pathlib import Path
import re
import unittest
from urllib.parse import parse_qs, urlparse

import yaml

ROOT=Path(__file__).resolve().parents[1]
SOURCE_BASE='https://github.com/3115a083/ha-blueprints/blob/main/'


class Loader(yaml.SafeLoader):
    pass


Loader.add_constructor('!input',lambda loader,node: '!input '+loader.construct_scalar(node))


class CatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.readme=(ROOT/'README.md').read_text()
        cls.paths=sorted((ROOT/'blueprints/automation').rglob('*.yaml'))

    def test_every_blueprint_has_its_own_updateable_source(self):
        self.assertTrue(self.paths)
        sources=[]
        for path in self.paths:
            with self.subTest(path=path.name):
                data=yaml.load(path.read_text(),Loader=Loader)
                source=data['blueprint']['source_url']
                self.assertEqual(source,SOURCE_BASE+path.relative_to(ROOT).as_posix())
                self.assertEqual(data['blueprint']['domain'],'automation')
                sources.append(source)
        self.assertEqual(len(sources),len(set(sources)))

    def test_catalog_contains_manual_url_and_matching_one_click_import(self):
        rows=[line for line in self.readme.splitlines() if line.startswith('| **')]
        self.assertEqual(len(rows),len(self.paths))
        for path in self.paths:
            source=SOURCE_BASE+path.relative_to(ROOT).as_posix()
            with self.subTest(path=path.name):
                row=next(line for line in rows if f'`{source}`' in line)
                self.assertEqual(len(row.strip("|").split("|")),5)
                redirect=re.search(r'\]\((https://my\.home-assistant\.io/redirect/blueprint_import/\?[^)]+)\)',row)
                self.assertIsNotNone(redirect)
                self.assertEqual(parse_qs(urlparse(redirect.group(1)).query)['blueprint_url'],[source])
                copy_link=re.search(r'\[Copy URL\]\(#([^)]+)\)',row)
                self.assertIsNotNone(copy_link)
                headings=re.findall(r'^### (.+)$',self.readme,re.M)
                self.assertIn(copy_link.group(1),[re.sub(r'[^a-z0-9 -]','',h.lower()).replace(' ','-') for h in headings])

    def test_copy_blocks_and_individual_guides_have_exact_urls(self):
        blocks=re.findall(r'```text\n([^\n]+)\n```',self.readme)
        for path in self.paths:
            source=SOURCE_BASE+path.relative_to(ROOT).as_posix()
            with self.subTest(path=path.name):
                self.assertEqual(blocks.count(source),1)
                guide=(path.parent/'README.md').read_text()
                self.assertIn('```text\n'+source+'\n```',guide)
                self.assertIn('blueprints_updater.reload',guide)
