@agent_test
Feature: LLM Chat Completion - AgenTest App

  Tests for the Groq-backed LLM gateway covering basic completion,
  tool calls, JSON mode, streaming, reasoning, and multi-turn chat.

  Background:
    Given I am testing application "agentest_app" for "api"
    And I set the headers
      | name         | value            |
      | Content-Type | application/json |

  # --- Basic / Health ---

  Scenario: Health check
    Given I set the base url from spec "health"
    And I append "/health" to the base url
    When I hit the GET api
    Then the status code should be 200

  # --- Non-streaming Chat Completion ---

  Scenario Outline: Chat completion with <variant> body
    Given I set the api body from spec "chat_completion" variant "<variant>"
    When I hit the POST api
    Then the status code should be <status>

    Examples:
      | variant      | status |
      | default      | 200    |
      | minimal      | 200    |
      | multi_turn   | 200    |
      | with_tools   | 200    |
      | json_mode    | 200    |
      | reasoning    | 200    |

  # --- Streaming ---

  Scenario: Streaming chat completion
    Given I set the api body from spec "streaming" variant "streaming"
    When I hit the POST api
    Then the status code should be 200

  # --- Body Override Tests ---

  Scenario: Override model and temperature
    Given I set the api body from spec "chat_completion" variant "default"
    And I update the api body at "model" to "llama-3.3-70b-versatile"
    And I update the api body at "temperature" to "0"
    And I update the api body at "max_completion_tokens" to "512"
    When I hit the POST api
    Then the status code should be 200

  Scenario: Override nested message content
    Given I set the api body from spec "chat_completion" variant "default"
    And I update the api body at "messages.0.content" to "You are a math tutor."
    And I update the api body at "messages.1.content" to "What is 2+2?"
    When I hit the POST api
    Then the status code should be 200

  Scenario: Override with JSON mode via table
    Given I set the base url from spec "chat_completion"
    And I set the api body
      | path                    | value                                |
      | model                   | openai/gpt-oss-120b                  |
      | messages.0.role         | system                               |
      | messages.0.content      | Respond in JSON                      |
      | messages.1.role         | user                                 |
      | messages.1.content      | Give me 3 fruits as a JSON array     |
      | temperature             | 0.3                                  |
      | response_format.type    | json_object                          |
    And I append "/v1/chat/completions" to the base url
    When I hit the POST api
    Then the status code should be 200

  # --- Tool Call Tests ---

  Scenario: Chat with tool definitions
    Given I set the api body from spec "chat_completion" variant "with_tools"
    And I update the api body at "messages.1.content" to "What is 15 * 23?"
    When I hit the POST api
    Then the status code should be 200

  # --- Reasoning Tests ---

  Scenario: High reasoning effort
    Given I set the api body from spec "chat_completion" variant "reasoning"
    When I hit the POST api
    Then the status code should be 200

  # --- Response Validation Tests ---

  Scenario: Validate response with expression table
    Given I set the api body from spec "chat_completion" variant "default"
    When I hit the POST api
    Then I validate the response
      | input                                    | expression                      |
      | status_code                              | int(a) == 200                  |
      | body.object                              | a == "chat.completion"         |
      | body.model                               | a == "openai/gpt-oss-120b"    |
      | body.choices.0.message.role              | a == "assistant"               |
      | body.usage.total_tokens                  | int(a) > 0                     |

  Scenario: Validate with multiple inputs and compound expression
    Given I set the api body from spec "chat_completion" variant "default"
    When I hit the POST api
    Then I validate the response
      | input                                    | expression                      |
      | status_code, body.object                 | int(a) == 200 and b == "chat.completion" |
      | body.model, body.choices.0.finish_reason | a == "openai/gpt-oss-120b" and b == "stop" |

  # --- Save Response Tests ---

  Scenario: Save response and verify in context
    Given I set the api body from spec "chat_completion" variant "default"
    When I hit the POST api
    Then I save the response in context
    And the context at "api_response.status_code" should be "200"
    And the context at "api_response.body.id" should be set
    And the context at "api_response.body.object" should be "chat.completion"

  Scenario: Save response to custom variable
    Given I set the api body from spec "chat_completion" variant "default"
    When I hit the POST api
    Then I save the response in context at "my_custom_response"
    And the context at "my_custom_response.status_code" should be "200"
    And the context at "my_custom_response.body.model" should be "openai/gpt-oss-120b"

  # --- Keyword Validation Tests ---

  Scenario: Validate with regex keyword
    Given I set the api body from spec "chat_completion" variant "default"
    When I hit the POST api
    Then I validate the response
      | input                                    | expression                               |
      | body.object                              | regex(r"chat[.]completion$", a)          |
      | body.model                               | regex("openai/", a)                      |
      | body.id                                  | regex("^chatcmpl-", a)                   |
      | body.choices.0.finish_reason             | regex("stop", a)                         |
      | body.usage.total_tokens                  | int(a) > 0 and int(a) < 1000             |

  @llm_validation
  Scenario: Validate with llm_binary keyword
    Given I set the api body from spec "chat_completion" variant "default"
    When I hit the POST api
    Then I validate the response
      | input                                    | expression                                                 |
      | body                                     | llm_binary("Is this a valid chat completion response?", str(a)) |
      | body.choices.0.message.content           | llm_binary("Does this look like a helpful assistant response?", a) |

  @llm_validation
  Scenario: Validate with llm_score keyword
    Given I set the api body from spec "chat_completion" variant "default"
    When I hit the POST api
    Then I validate the response
      | input                                    | expression                                        |
      | body.choices.0.message.content           | llm_score("How relevant is this response?", a) > 0.5 |

  Scenario: Validate with re module directly
    Given I set the api body from spec "chat_completion" variant "default"
    When I hit the POST api
    Then I validate the response
      | input                                    | expression                               |
      | body.object                              | re.search(r"chat", a) is not None        |
      | body.model                               | re.fullmatch(r"openai/.*", a) is not None |
      | body.id                                  | re.match(r"chatcmpl", a) is not None     |
      | body.usage.total_tokens                  | int(a) > 0                              |

  @llm_validation
  Scenario: Validate with multi-value llm_binary
    Given I set the api body from spec "chat_completion" variant "default"
    When I hit the POST api
    Then I validate the response
      | input                                                  | expression                                                                      |
      | body.object, body.choices.0.message.role               | llm_binary("Are these fields consistent with a chat completion response?", a, b) |
      | body.model, body.choices.0.finish_reason               | llm_binary("Do the model and finish reason make sense together?", a, b)          |

  @llm_validation
  Scenario: Validate with named prompt file (test dir)
    Given I set the api body from spec "chat_completion" variant "default"
    When I hit the POST api
    Then I validate the response
      | input                                    | expression                                              |
      | body                                     | llm_binary("chat_completion_check", str(a))             |

  @llm_validation
  Scenario: Validate with built-in prompt (response_quality)
    Given I set the api body from spec "chat_completion" variant "default"
    When I hit the POST api
    Then I validate the response
      | input                                    | expression                                              |
      | body                                     | llm_binary("response_quality", str(a))                  |

  @llm_validation
  Scenario: Score with built-in prompt (response_score)
    Given I set the api body from spec "chat_completion" variant "default"
    When I hit the POST api
    Then I validate the response
      | input                                    | expression                                              |
      | body                                     | llm_score("response_score", str(a)) > 0.0               |
