
    
    

with all_values as (

    select
        source as value_field,
        count(*) as n_records

    from `deprem-502519`.`staging_marts`.`dm_earthquake_daily`
    group by source

)

select *
from all_values
where value_field not in (
    'usgs','kandilli','unified'
)


