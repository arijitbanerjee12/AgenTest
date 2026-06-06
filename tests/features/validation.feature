@agent_test
Feature: Response Validation

  All validation strategies for API responses: expression tables,
  regex, re module, LLM binary/score, named prompts, direct paths.

  Background:
    Given I am testing application "agentest_app" for "api"
    And I set the headers
      | name         | value            |
      | Content-Type | application/json |
    And I set the api body from spec "chat_completion" variant "default"

  # --- Expression Table ---

  Scenario: Basic expression table
    When I hit the POST api
    Then I validate the response
      | input                                    | expression                      |
      | status_code                              | int(a) == 200                  |
      | body.object                              | a == "chat.completion"         |
      | body.model                               | a == "openai/gpt-oss-120b"    |
      | body.choices.0.message.role              | a == "assistant"               |
      | body.usage.total_tokens                  | int(a) > 0                     |

  Scenario: Multiple inputs and compound expression
    When I hit the POST api
    Then I validate the response
      | input                                    | expression                      |
      | status_code, body.object                 | int(a) == 200 and b == "chat.completion" |
      | body.model, body.choices.0.finish_reason | a == "openai/gpt-oss-120b" and b == "stop" |

  # --- Regex ---

  Scenario: Regex keyword
    When I hit the POST api
    Then I validate the response
      | input                                    | expression                               |
      | body.object                              | regex(r"chat[.]completion$", a)          |
      | body.model                               | regex("openai/", a)                      |
      | body.id                                  | regex("^chatcmpl-", a)                   |
      | body.choices.0.finish_reason             | regex("stop", a)                         |

  Scenario: Re module directly
    When I hit the POST api
    Then I validate the response
      | input                                    | expression                               |
      | body.object                              | re.search(r"chat", a) is not None        |
      | body.model                               | re.fullmatch(r"openai/.*", a) is not None |
      | body.id                                  | re.match(r"chatcmpl", a) is not None     |

  # --- LLM Validation ---

  @agent_test2
  Scenario: LLM binary validation
    When I hit the POST api
    Then I validate the response
      | input                                    | expression                                                 |
      | body                                     | llm_binary("Is this a valid chat completion response?", str(a)) |
      | body.choices.0.message.content           | llm_binary("Does this look like a helpful assistant response?", a) |

  @agent_test2
  Scenario: LLM score validation
    When I hit the POST api
    Then I validate the response
      | input                                    | expression                                        |
      | body.choices.0.message.content           | llm_score("How relevant is this response?", a) > 0.5 |

  @agent_test2
  Scenario: Multi-value LLM binary
    When I hit the POST api
    Then I validate the response
      | input                                                  | expression                                                                      |
      | body.object, body.choices.0.message.role               | llm_binary("Are these fields consistent with a chat completion response?", a, b) |
      | body.model, body.choices.0.finish_reason               | llm_binary("Do the model and finish reason make sense together?", a, b)          |

  @agent_test2
  Scenario: Named prompt from test directory
    When I hit the POST api
    Then I validate the response
      | input                                    | expression                                              |
      | body                                     | llm_binary("chat_completion_check", str(a))             |

  @agent_test2
  Scenario: Direct file path in expression
    When I hit the POST api
    Then I validate the response
      | input                                    | expression                                              |
      | body                                     | llm_binary("tests/prompts/validation/chat_completion_check.txt", str(a)) |

  @agent_test2
  Scenario: Built-in prompt response_quality
    When I hit the POST api
    Then I validate the response
      | input                                    | expression                                              |
      | body                                     | llm_binary("response_quality", str(a))                  |

  @agent_test2
  Scenario: Built-in prompt response_score
    When I hit the POST api
    Then I validate the response
      | input                                    | expression                                              |
      | body                                     | llm_score("response_score", str(a)) > 0.0               |
