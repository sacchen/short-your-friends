  ## 1. Understand the Architecture Pattern

  Read through src/engine/interface.py and identify:
  - What is EngineCommand? (hint: it's a data structure)
  EngineCommand is a class with variables. It stores the information about an order. Also called DTO Data Transfer Object
  - What is EngineInterface? (hint: it's a coordinator class)
  EngineInterface is the layer between Engine and Economy. It calls the operations that the orders need to go through.
  - What does translate_client_message() do? (hint: converts API format → engine format)
  Since Server uses JSON and Engine uses ints, translate_client_message() does the conversion within this Interface class.

  Try this: Draw a diagram showing: Client → Server → Interface → Engine

  ## 2. Compare Old vs New

  Look at how server.py currently handles a request (lines 221-393 for _handle_place_order):
  - Count how many responsibilities it has (economy checks, ID mapping, engine calls, auditing, trade confirmation)
  Currently Server places orders in the Engine, parse market data, does the type conversions between Server and Engine, locks funds for Economy, creates markets, executes orders in Engine, run Audits, do settlements, handle price improvements, handle Persistence, and seed the data for tests.

  - Now look at EngineInterface._handle_place_order() in interface.py (lines 248-354)
  ._handle_place_order() now does all the interfacing with Economy, including locking funds, execute matching in Engine, confirm trades in Economy, handle price improvement refunds, and runs audits.

  - What's different? What moved where?
  A bunch of Server's jobs moved to ._handle_place_order(). Server just sends the Commands and Interface does the coordination with Engine and Economy.

  ## 3. Fix It Yourself

  Try to fix the integration in server.py. You'll need to:

  Step A: Modify __init__() to create an EngineInterface instance

  Step B: Fix process_request() to:
  - Call translate_client_message() with the right parameters
  - Call the interface's execute() method correctly

  Step C: Delete the old dead code (lines 138-176 and the old handler methods)

  ## 4. Test Your Understanding

  After fixing it, ask:
  - Why is this separation better?
  - What did the old code do that the new code also does?
  - What bugs could this prevent?