
    
    

with all_values as (

    select
        source as value_field,
        count(*) as n_records

    from `deprem-502519`.`staging`.`stg_kandilli_earthquakes`
    group by source

)

select *
from all_values
where value_field not in (
    'kandilli'
)


