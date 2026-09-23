select
    {{ dbt_utils.generate_surrogate_key(['unitid', 'year']) }} as institution_key,
    unitid,
    year,
    institution_name,
    state
from {{ ref('stg_institutions') }}
