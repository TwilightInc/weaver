# that's all?
import json
with open("test_extension/manifest.json", "r") as raw_manifest:
    manifest = json.load(raw_manifest)
print('Manifest', f'V{manifest['manifest_version']}', 'extension')
print('Extension name:', manifest['name'])
print('Extension version:', manifest['version'])
print('Extension description:', manifest['description'])
print('Extension icons:', manifest['icons'])
print('Extension browser action:', manifest['browser_action'])
print('Extension permissions:', manifest['permissions'])