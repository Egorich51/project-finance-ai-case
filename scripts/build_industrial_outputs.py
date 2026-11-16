"""Recreate three financial models and conclusions from the supplied archive."""
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.industrial_finance import audit_project
from src.industrial_outputs import write_industrial_outputs


def main():
    root=Path(__file__).resolve().parents[1]/'studies/industrial-v2'
    for source in sorted((root/'input').glob('*/Входные данные.json')):
        data=json.loads(source.read_text(encoding='utf-8'))
        result=audit_project(data)
        write_industrial_outputs(data,result,root/'outputs'/source.parent.name)
        print(data['id'],'loan',result['loan'],'min DSCR',round(result['min_dscr_repayment'],6),'NPV',round(result['npv'],6),'max source difference',result['max_reference_difference'])


if __name__=='__main__':main()
