import os, importlib.util
wd = r"c:\Users\killr\OneDrive\Dokumente\boardgames\magic\printingScript"
os.chdir(wd)
mtg = os.path.join(wd, 'mtg_test')
os.makedirs(mtg, exist_ok=True)
with open(os.path.join(mtg, 'cards.xml'), 'w', encoding='utf-8') as f:
    f.write('<root><fronts></fronts></root>')
print('Test setup created at', mtg)
# Import Print_cards_sm
spec = importlib.util.spec_from_file_location('pcs', os.path.join(wd, 'Print_cards_sm.py'))
pcs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pcs)
# Import reprint
spec2 = importlib.util.spec_from_file_location('rp', os.path.join(wd, 'reprint.py'))
rp = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(rp)
print('Imported modules OK')
