RESOLVE_PREFIX = 'resolve_'
POST_PREFIX = 'post_'
PYDANTIC_FORWARD_REF_UPDATED = '__pydantic_resolve_forward_refs_updated__'
HAS_MAPPER_FUNCTION = '__pydantic_resolve_mapper_provided__'
POST_DEFAULT_HANDLER = 'post_default_handler'

EXPOSE_TO_DESCENDANT = '__pydantic_resolve_expose__'
COLLECTOR_CONFIGURATION = '__pydantic_resolve_collect__'

ENSURE_SUBSET_REFERENCE = '__pydantic_resolve_ensure_subset_reference__'
ENSURE_SUBSET_DEFINITION = '__pydantic_resolve_subset__'
ENSURE_SUBSET_DEFINITION_SHORT = '__subset__'

ER_DIAGRAM = '__pydantic_resolve_er_diagram__'
ER_DIAGRAM_PRE_GENERATOR = '__pydantic_resolve_er_diagram_pre_gen__'
ER_DIAGRAM_INLINE_RELATIONSHIPS = '__relationships__'

# GraphQL method metadata attributes.
# These keys are attached to method functions by GraphQL decorators
# and by ErDiagram QueryConfig/MutationConfig dynamic binding.
GRAPHQL_QUERY_ATTR = '_pydantic_resolve_query'
# Optional explicit GraphQL operation name override for queries.
GRAPHQL_QUERY_NAME_ATTR = '_pydantic_resolve_query_name'
# Operation description used by SDL/introspection outputs.
GRAPHQL_QUERY_DESCRIPTION_ATTR = '_pydantic_resolve_query_description'

GRAPHQL_MUTATION_ATTR = '_pydantic_resolve_mutation'
# Optional explicit GraphQL operation name override for mutations.
GRAPHQL_MUTATION_NAME_ATTR = '_pydantic_resolve_mutation_name'
# Operation description used by SDL/introspection outputs.
GRAPHQL_MUTATION_DESCRIPTION_ATTR = '_pydantic_resolve_mutation_description'

# Marks methods dynamically bound from config to avoid
# conflict with decorator-defined methods of the same name.
GRAPHQL_CONFIG_BOUND_ATTR = '_pydantic_resolve_config_bound'
