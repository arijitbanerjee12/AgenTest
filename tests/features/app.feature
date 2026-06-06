Feature: Application-specific spec loading

  Scenario: Load spec from app-specific api config
    Given I am testing application "dummyapp" for "api"
    And I set the base url to "https://jsonplaceholder.typicode.com"
    And I set the headers
      | name         | value            |
      | Content-Type | application/json |
      | Accept       | application/json |
    And I set the api body from spec "create_post"
    When I hit the POST api
    Then the status code should be 201

  Scenario: App context persists across spec loads
    Given I am testing application "dummyapp" for "api"
    And I set the base url to "https://jsonplaceholder.typicode.com"
    And I set the headers
      | name         | value            |
      | Content-Type | application/json |
    And I set the api body from spec "create_post" variant "custom"
    When I hit the POST api
    Then the status code should be 201
