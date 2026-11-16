"""Recalculate all three models with a supplied LibreOffice and verify numbers."""
import argparse
import json
import subprocess
import tempfile
import sys
from pathlib import Path

from openpyxl import load_workbook


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--soffice',required=True)
    parser.add_argument('--output',type=Path,default=Path('.qa/industrial-excel'))
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]/'studies/industrial-v2'
    total=0
    for source in sorted((root/'outputs').glob('*/audit.json')):
        expected=json.loads(source.read_text())
        destination=args.output/source.parent.name
        destination.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='industrial-lo-') as profile:
            run=subprocess.run([args.soffice,f'-env:UserInstallation={Path(profile).as_uri()}','--headless','--convert-to','xlsx','--outdir',str(destination),str(source.parent/'financial-model.xlsx')],capture_output=True,text=True,timeout=90)
            if run.returncode:raise RuntimeError(run.stdout+run.stderr)
        book=load_workbook(destination/'financial-model.xlsx',data_only=True)
        def check(sheet,cell,value):
            nonlocal total
            actual=book[sheet][cell].value
            if not isinstance(actual,(int,float)) or abs(actual-value)>1e-7:
                raise AssertionError((source.parent.name,sheet,cell,actual,value))
            total+=1
        for row,item in enumerate(expected['monthly'],8):
            for col,key in {'C':'draw','D':'debt_opening','E':'interest','F':'principal','G':'debt_closing','H':'debt_service'}.items():check('Кредит',f'{col}{row}',item[key])
            for col,key in {'C':'ebitda','D':'tax','E':'change_nwc','F':'maintenance','G':'equity','H':'capex','I':'vat_refund','J':'cfads','K':'cash_change','L':'cash','M':'stress_cfads','N':'stress_cash'}.items():check('Потоки',f'{col}{row}',item[key])
        for index,item in enumerate(expected['annual']):
            col=chr(66+index)
            for row,key in {6:'ebitda',7:'tax',8:'change_nwc',9:'maintenance',10:'interest',11:'principal',12:'cfads',13:'debt_service',14:'dscr',15:'debt_closing',16:'cash',17:'stress_cfads',18:'stress_dscr',19:'stress_cash'}.items():check('Годы',f'{col}{row}',item[key])
        for row,key in {5:'budget',6:'loan',7:'equity',8:'min_dscr_repayment',9:'min_dscr_all',10:'minimum_cash',11:'npv',12:'irr',13:'stress_min_dscr_repayment',14:'stress_minimum_cash',15:'base_screening_limit',16:'stress_screening_limit'}.items():check('Выводы',f'B{row}',expected[key])
        check('Экономика','B12',expected['npv']);check('Экономика','B13',expected['irr'])
        errors=[(s.title,c.coordinate,c.value) for s in book for row in s for c in row if c.data_type=='e']
        if errors:raise AssertionError(errors)
        book.close()
        print('Verified',source.parent.name,flush=True)
    print('Verified numeric cells:',total)


if __name__=='__main__':main()
