
    
    

with dbt_test__target as (

  select match_id as unique_field
  from `deprem-502519`.`staging`.`int_earthquake_matches`
  where match_id is not null

)

select
    unique_field,
    count(*) as n_records

from dbt_test__target
group by unique_field
having count(*) > 1


