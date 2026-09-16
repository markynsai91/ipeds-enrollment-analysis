import pandas as pd
from pathlib import Path

frames=[]

for path in sorted(Path('raw').glob('ef*a.csv')):
    df = pd.read_csv(path)
    df['year'] = int(path.name[2:6])
    frames.append(df)

enrollment=pd.concat(frames,ignore_index=True)

enrollment = enrollment[['UNITID', 'year', 'EFALEVEL', 'EFTOTLT', 'XEFTOTLT']]

enrollment = enrollment[enrollment['EFALEVEL'] == 1]
enrollment['is_imputed'] = enrollment['XEFTOTLT'] != 'R'

enrollment = enrollment.rename(columns={
    'UNITID': 'unitid',
    'EFTOTLT': 'total_enrollment'
})

enrollment = enrollment.drop(columns=['EFALEVEL', 'XEFTOTLT'])

print(enrollment.shape)
print(enrollment['year'].value_counts())

Path('processed').mkdir(exist_ok=True)

enrollment.to_parquet('processed/enrollment.parquet', index=False)

print(f"Wrote {len(enrollment)} rows to processed/enrollment.parquet")

hd_frames = []

for path in sorted(Path('raw').glob('hd*.csv')):
    df = pd.read_csv(path, encoding='latin-1')
    df.columns = df.columns.str.replace('ï»¿', '', regex=False).str.strip()
    df['year'] = int(path.name[2:6])
    hd_frames.append(df)

institutions = pd.concat(hd_frames, ignore_index=True)

print(institutions.shape)

institutions = institutions[['UNITID', 'year', 'INSTNM', 'STABBR']]
institutions = institutions.dropna(subset=['UNITID'])
institutions['UNITID'] = institutions['UNITID'].astype('int64')

institutions = institutions.rename(columns={
    'UNITID': 'unitid',
    'INSTNM': 'institution_name',
    'STABBR': 'state'
})

institutions.to_parquet('processed/institutions.parquet', index=False)

print(f"Wrote {len(institutions)} rows to processed/institutions.parquet")


