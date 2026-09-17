select
    unitid,
    year,
    total_enrollment,
    is_imputed
from read_parquet('../processed/enrollment.parquet')
