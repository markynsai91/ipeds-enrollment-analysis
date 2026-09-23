select
    d.institution_key,
    e.year,
    e.total_enrollment,
    e.is_imputed
from {{ ref('stg_enrollment') }} e
left join {{ ref('dim_institutions') }} d
  on e.unitid = d.unitid
 and e.year = d.year
