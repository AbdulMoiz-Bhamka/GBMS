from app.modules.roles.repository import get_role_id as repository_get_role_id


def get_role_id(cursor, role_name):
    return repository_get_role_id(cursor, role_name)
