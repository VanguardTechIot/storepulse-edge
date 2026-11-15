"""Anti-corruption layer the IAM bounded context offers to the other contexts.

Other bounded contexts reach IAM only through this package, which answers with
primitive values so they never depend on the IAM domain model.
"""
