I want to add a new spec for these Jedi MCP to do the following:

1. Extend the existing SQLite with vector db extension. 

2. The markdown summary is vectorize for seach capability.

3. All the scrape documents are stored separately as a silver layer (Medallion architecture) within the same SQLite. May be used for search in the future.

4. Add a searchDoc tools to search from the summary to retrieve the exact context of the search keyword.

5. Add loadDoc tool to retrive the full summary. The parameters can be obtain from the slug returned by the searchDoc tool.

6. Improve the summary generation so that it contains keywords that the searchDoc tool is able to retrieve relavent context accurately.

7. Add a listDoc tool so that we can view the list of topics in the doc for AI to use to retrieve information.

8. Not that, there is not upper limit of how much data can be stored. Feel free to use as much space as you need so that the context is intact. While removing all the duplicates stuff. (Suggest to break it down by smaller topics/name)