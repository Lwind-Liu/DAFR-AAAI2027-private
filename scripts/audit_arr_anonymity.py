from pathlib import Path
import re, json
root=Path(__file__).resolve().parents[1]
files=[root/'paper/naacl/DAFR_NAACL2027_Main.tex', root/'paper/naacl/DAFR_NAACL2027_Appendix.tex']
patterns={
 'personal_paths': r'(/Users/|/home/|[A-Za-z]:\\Users\\)',
 'emails': r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}',
 'github_or_cloud': r'(github\.com|gitlab\.com|drive\.google|dropbox\.com)',
 'named_affiliation': r'\\affiliation|\\institute|\\university|\\author\{(?!Anonymous)',
}
findings=[]
for f in files:
 s=f.read_text(errors='replace')
 for name,pat in patterns.items():
  for m in re.finditer(pat,s,re.I):
   findings.append({'file':str(f.relative_to(root)),'kind':name,'match':m.group(0)[:100],'line':s[:m.start()].count('\n')+1})
print(json.dumps({'files':[str(f.relative_to(root)) for f in files], 'findings':findings, 'passed':not findings}, indent=2))
