
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
        select *
        from `deprem-502519`.`staging_dbt_test__audit`.`accepted_values_stg_usgs_earthquakes_source__usgs`
    
      
    ) dbt_internal_test