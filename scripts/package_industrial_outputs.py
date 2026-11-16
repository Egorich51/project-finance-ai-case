"""Package published financial models and conclusions for a single download."""
import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT=Path(__file__).resolve().parents[1]/'studies/industrial-v2'


def main():
    files=sorted(p for p in (ROOT/'outputs').rglob('*') if p.is_file())
    if len(files)!=12:
        raise ValueError('Expected three complete four-file bundles')
    manifest={str(p.relative_to(ROOT/'outputs')):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    with ZipFile(ROOT/'deliverables.zip','w',ZIP_DEFLATED) as archive:
        for path in files:archive.write(path,path.relative_to(ROOT/'outputs'))
        archive.writestr('SHA256.json',json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
        archive.writestr('README.txt','Три синтетических промышленных проекта. В каждой папке: Excel с формулами, Word-заключение, текст заключения и числовой аудит. Деньги в млн рублей.\n\nИсследование, исходные данные и ответы моделей:\nhttps://github.com/Egorich51/project-finance-ai-case/blob/build-case/studies/industrial-v2/REPORT.md\n\nФинансовые модели рассчитаны по JSON автора; ответы LLM оценены отдельно. Реалистичность операционных предпосылок не подтверждалась. Предварительная техническая проверка, не одобрение кредита.\n')
    print('Packaged',len(files),'files')


if __name__=='__main__':main()
