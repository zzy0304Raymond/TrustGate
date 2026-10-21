import copy
import json
import re
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch
from scripts.demo import build


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__();self.tags=[];self.links=[];self.ids=[]
    def handle_starttag(self,tag,attrs):
        self.tags.append(tag)
        for key,value in attrs:
            if key in ('src','href'):self.links.append(value)
            if key=='id':self.ids.append(value)


class DemoTests(unittest.TestCase):
    def test_recorded_cases_are_separate_from_controls(self):
        data=build.verify_bundle()
        self.assertEqual(data['mode'],'recorded_trace_walkthrough')
        self.assertEqual(data['new_model_requests'],0)
        self.assertEqual([c['id'] for c in data['cases']],['normal','defense','false-positive'])
        self.assertEqual(len({cid for c in data['cases'] for cid in c['case_ids']}),6)

    def test_static_page_needs_no_network_or_scripts(self):
        page=PageParser();page.feed((build.DEMO/'index.html').read_text())
        self.assertNotIn('script',page.tags)
        self.assertNotIn('iframe',page.tags)
        self.assertEqual(len(page.ids),len(set(page.ids)))
        self.assertEqual(set(page.links),{'#normal','#defense','#false-positive'})
        self.assertTrue(all(link[1:] in page.ids for link in page.links))

    def test_render_escapes_text_and_case_ids(self):
        data=copy.deepcopy(build.build_data())
        data['cases'][0]['title']='<img src=x onerror=alert(1)>'
        data['cases'][0]['case_ids']=['<script>alert(1)</script>']
        output=build.render(data)
        self.assertNotIn('<img',output)
        self.assertNotIn('<script',output)
        self.assertIn('&lt;script&gt;',output)

    def test_factual_error_does_not_replace_native_score(self):
        record=build.build_data()['cases'][2]
        self.assertTrue(record['facts']['native_utility'])
        self.assertTrue(record['facts']['confirmed_factual_conflict'])
        self.assertFalse(record['facts']['attack_present'])
        self.assertNotEqual(record['facts']['current_day'],record['facts']['queried_day'])

    def test_contradictory_defense_evidence_is_rejected(self):
        original=build.read
        def changed(path):
            obj=original(path)
            if str(path).endswith(f'{build.DEFENSE}/evidence.json'):
                obj['tool_calls'][1]['executed']=True
            return obj
        with patch.object(build,'read',side_effect=changed):
            with self.assertRaises(AssertionError):build.build_data()

    def test_changed_output_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);demo=root/'demos';demo.mkdir()
            (demo/'cases.json').write_text('changed')
            (demo/'manifest.json').write_text(json.dumps({'inputs':{},'outputs':{'cases.json':'0'*64}}))
            with patch.multiple(build,ROOT=root,DEMO=demo):
                with self.assertRaisesRegex(ValueError,'Demo output differs'):build.verify_bundle()

    def test_manifest_cannot_reference_outside_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);demo=root/'demos';demo.mkdir()
            (demo/'manifest.json').write_text(json.dumps({'inputs':{},'outputs':{'../outside':'0'*64}}))
            with patch.multiple(build,ROOT=root,DEMO=demo):
                with self.assertRaisesRegex(ValueError,'Demo output differs'):build.verify_bundle()

    def test_document_links_resolve(self):
        for name in ('demos/README_ZH.md','docs/DEMO_WALKTHROUGH_ZH.md'):
            path=build.ROOT/name
            for link in re.findall(r'\]\(([^)]+)\)',path.read_text()):
                if not link.startswith(('http:', 'https:', '#')):
                    self.assertTrue((path.parent/link.split('#')[0]).exists(),(name,link))

    def test_published_controls_are_explicitly_scripted(self):
        data=build.read(build.ROOT/'results/demo/mcp_checks.json')
        self.assertEqual(data['mode'],'scripted_agent_loop_with_real_mcp')
        self.assertEqual(data['new_model_requests'],0)
        self.assertEqual(data['checker_sha256'],build.sha(build.ROOT/'scripts/demo/check_mcp.py'))
        self.assertEqual(data['bundle_manifest_sha256'],build.sha(build.DEMO/'manifest.json'))
        records={r['control']:r for r in data['records']}
        self.assertEqual(len(records),6)
        self.assertTrue(records['defense-trustgate']['exact_goal_call_blocked'])
        self.assertFalse(records['defense-trustgate']['exact_attack_success'])
        self.assertTrue(records['defense-no_authorization']['exact_attack_success'])


if __name__=='__main__':unittest.main()
