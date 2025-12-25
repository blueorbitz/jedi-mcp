#!/usr/bin/env python3
"""
Simple integration test to verify vector search functionality works.
"""

import tempfile
from pathlib import Path
from jedi_mcp.vector_database import VectorDatabaseManager
from jedi_mcp.models import EmbeddingConfig
from jedi_mcp.mcp_server import create_mcp_server

def test_vector_integration():
    """Test that vector search integration works end-to-end."""
    
    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    
    try:
        # Initialize vector database
        db_manager = VectorDatabaseManager(db_path)
        embedding_config = EmbeddingConfig()
        project_name = "test-integration"
        
        # Initialize vector schema
        db_manager.initialize_vector_schema(project_name, embedding_config)
        
        # Create MCP server
        mcp_server = create_mcp_server(project_name, db_manager=db_manager)
        
        # Check that vector search tools are registered
        tools_dict = mcp_server._tool_manager._tools
        tool_names = list(tools_dict.keys())
        
        print(f"✅ MCP server created successfully")
        print(f"📊 Registered tools: {len(tool_names)}")
        print(f"🔍 Tools: {', '.join(tool_names)}")
        
        # Verify vector search tools are present
        expected_tools = ["searchDoc", "loadDoc", "listDoc"]
        for tool in expected_tools:
            if tool in tool_names:
                print(f"✅ {tool} tool registered")
            else:
                print(f"❌ {tool} tool missing")
                return False
        
        # Test that tools can be invoked without errors
        try:
            search_tool = tools_dict["searchDoc"]
            result = search_tool.fn("test query")
            print(f"✅ searchDoc tool invocation successful")
            
            list_tool = tools_dict["listDoc"]
            result = list_tool.fn()
            print(f"✅ listDoc tool invocation successful")
            
        except Exception as e:
            print(f"❌ Tool invocation failed: {e}")
            return False
        
        print(f"🎉 Integration test passed!")
        return True
        
    finally:
        # Cleanup
        if db_path.exists():
            db_path.unlink()

if __name__ == "__main__":
    success = test_vector_integration()
    exit(0 if success else 1)