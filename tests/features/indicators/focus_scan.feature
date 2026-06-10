@focus_scan @indicator_test
Feature: Focus Scan — ETFs + Top 30 Large Caps

  BDD scan limited to the user's focus universe.
  Each stock is a separate test case.
  Passes (green) if BUY or SELL signal detected.

  @etf
  Scenario: Focus ETF scan
    Given I configure EMA indicators
      | period | field |
      | 10     | Close |
      | 20     | Close |
    And I select data granularity "daily"
    When I analyze stock for "3y"
    Then I check signal in category "etf"

  @large_cap_focus
  Scenario: Focus Large Cap scan
    Given I configure EMA indicators
      | period | field |
      | 10     | Close |
      | 20     | Close |
    And I select data granularity "daily"
    When I analyze stock for "3y"
    Then I check signal in category "large_cap"

  @summary @focus_scan
  Scenario: Focus Scan Summary Dashboard
    Then I generate cumulative scan dashboard
