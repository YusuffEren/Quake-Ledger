
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
        select *
        from `deprem-502519`.`staging_dbt_test__audit`.`test_min_events_recent`
    
      
    ) dbt_internal_test