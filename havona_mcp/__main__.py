"""Entry point: python -m havona_mcp"""
import sys
from .server import mcp

if __name__ == "__main__":
    transport = "sse" if "--sse" in sys.argv else "stdio"
    mcp.run(transport=transport)
