
    
    

with all_values as (

    select
        match_status as value_field,
        count(*) as n_records

    from `deprem-502519`.`staging`.`int_earthquake_matches`
    group by match_status

)

select *
from all_values
where value_field not in (
    'matched','usgs_only','kandilli_only'
)


