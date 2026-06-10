@btst_scan @indicator_test
Feature: BTST (Buy Today Sell Tomorrow) — Hourly EMA 10/20 + Heikin-Ashi

  Last-hour signal detection for Nifty, Bank Nifty, Sensex + top 10 large caps.
  Entry at day T close, exit at day T+1 close.
  Includes options P&L approximation (ATM, ~18x multiplier).

  @btst_scan
  Scenario: Run BTST backtest
    Given I have BTST symbols configured
    When I run BTST backtest for "3mo"
    Then I generate BTST signals report

  @summary @btst_scan
  Scenario: BTST Summary Dashboard
    Then I generate BTST dashboard
