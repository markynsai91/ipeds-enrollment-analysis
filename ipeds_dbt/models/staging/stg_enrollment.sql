select
    unitid,
    year,
    total_enrollment,
    is_imputed
from {{ source('ipeds', 'enrollment') }}
