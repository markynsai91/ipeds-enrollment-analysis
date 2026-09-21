select
    unitid,
    year,
    institution_name,
    state
from {{ source('ipeds', 'institutions') }}
