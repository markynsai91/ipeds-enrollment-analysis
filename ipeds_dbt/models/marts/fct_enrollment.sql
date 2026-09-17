select
    e.unitid,
    e.year,
    i.institution_name,
    i.state,
    e.total_enrollment,
    e.is_imputed
from {{ ref('stg_enrollment') }} e
join {{ ref('stg_institutions') }} i
  on e.unitid = i.unitid
 and e.year = i.year