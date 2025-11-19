from mcp.server.fastmcp import FastMCP

#  Stateful server (maintains session state)
mcp = FastMCP("StatefulServer")

#  Stateless server (no session persistence)
mcp = FastMCP("StatelessServer", stateless_http = True)

#  Stateless server (no session persistence, no sse stream with supported client)
mcp = FastMCP("StatelessServer", stateless_http = True, json_response = True)

#  Run server with streamable_http transport
mcp.run(transport="streamable-http")