"""
GraphiQL IDE HTML template.

Provides a ready-to-use GraphiQL page that can be served alongside the GraphQL endpoint.
"""

_GRAPHIQL_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
  <style>
    body {{ margin: 0; }}
    #graphiql {{ height: 100dvh; }}
    .loading {{
      height: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 2rem;
    }}
  </style>
  <link rel="stylesheet" href="https://esm.sh/graphiql/dist/style.css" />
  <link rel="stylesheet" href="https://esm.sh/@graphiql/plugin-explorer/dist/style.css" />
  <script type="importmap">
    {{
      "imports": {{
        "react": "https://esm.sh/react@19.1.0",
        "react/jsx-runtime": "https://esm.sh/react@19.1.0/jsx-runtime",
        "react-dom": "https://esm.sh/react-dom@19.1.0",
        "react-dom/client": "https://esm.sh/react-dom@19.1.0/client",
        "@emotion/is-prop-valid": "data:text/javascript,",
        "graphiql": "https://esm.sh/graphiql?standalone&external=react,react-dom,@graphiql/react,graphql",
        "graphiql/": "https://esm.sh/graphiql/",
        "@graphiql/plugin-explorer": "https://esm.sh/@graphiql/plugin-explorer?standalone&external=react,@graphiql/react,graphql",
        "@graphiql/react": "https://esm.sh/@graphiql/react?standalone&external=react,react-dom,graphql,@emotion/is-prop-valid",
        "@graphiql/toolkit": "https://esm.sh/@graphiql/toolkit?standalone&external=graphql",
        "graphql": "https://esm.sh/graphql@16.11.0"
      }}
    }}
  </script>
</head>
<body>
  <div id="graphiql">
    <div class="loading">Loading&hellip;</div>
  </div>
  <script type="module">
    import React from 'react';
    import ReactDOM from 'react-dom/client';
    import {{ GraphiQL, HISTORY_PLUGIN }} from 'graphiql';
    import {{ createGraphiQLFetcher }} from '@graphiql/toolkit';
    import {{ explorerPlugin }} from '@graphiql/plugin-explorer';

    const fetcher = createGraphiQLFetcher({{ url: '{endpoint}' }});
    const plugins = [HISTORY_PLUGIN, explorerPlugin()];

    function App() {{
      return React.createElement(GraphiQL, {{
        fetcher: fetcher,
        plugins: plugins,
      }});
    }}

    const container = document.getElementById('graphiql');
    const root = ReactDOM.createRoot(container);
    root.render(React.createElement(App));
  </script>
</body>
</html>
"""


def get_graphiql_html(
    endpoint: str = "/graphql",
    title: str = "GraphiQL",
) -> str:
    """Return an HTML page that hosts the GraphiQL IDE.

    Args:
        endpoint: URL of the GraphQL query endpoint (POST). Defaults to ``"/graphql"``.
        title: Browser tab title. Defaults to ``"GraphiQL"``.

    Returns:
        Complete HTML string suitable for an ``HTMLResponse``.
    """
    return _GRAPHIQL_HTML.format(endpoint=endpoint, title=title)
