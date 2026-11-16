"""Account: one person who can sign in to the web app."""

import re


class Account:
    """An email, a display name and a role (admin or officer).

    An Account() with nothing given is an unset account (empty email and name); otherwise
    the email, the name and the role must all be valid.
    """

    ADMIN: str = "admin"
    OFFICER: str = "officer"
    ROLES: tuple[str, ...] = (ADMIN, OFFICER)
    __EMAIL_PATTERN: str = r"^[a-z0-9._-]+@[a-z0-9.-]+\.[a-z]+$"
    __NAME_PATTERN: str = r"^[A-Za-z][A-Za-z .'-]*$"
    MIN_NAME: int = 2
    MAX_NAME: int = 40

    def __init__(self, email: str = "", name: str = "", role: str = "officer") -> None:
        """Raises ValueError, saying what is wrong and what is allowed, for a bad value. Empty email and
        name are allowed only together (an unset account)."""
        if not isinstance(email, str) or not isinstance(name, str):
            raise ValueError("An account's email and name must be text.")
        email = email.strip().lower()
        name = name.strip()
        if role not in Account.ROLES:
            raise ValueError(f"The role must be one of {', '.join(Account.ROLES)} (got {role!r}).")
        if email or name:
            if not re.match(Account.__EMAIL_PATTERN, email):
                raise ValueError("The email must look like name@example.com, in letters, digits, dots, "
                                 f"dashes or underscores (got {email!r}).")
            if not (Account.MIN_NAME <= len(name) <= Account.MAX_NAME) or not re.match(Account.__NAME_PATTERN, name):
                raise ValueError(f"The name must be {Account.MIN_NAME} to {Account.MAX_NAME} characters of "
                                 f"letters, spaces and . ' - (got {name!r}).")
        self.__email: str = email
        self.__name: str = name
        self.__role: str = role

    @property
    def email(self) -> str:
        return self.__email

    @property
    def name(self) -> str:
        return self.__name

    @property
    def role(self) -> str:
        return self.__role

    def is_admin(self) -> bool:
        """True for the admin account."""
        return self.__role == Account.ADMIN

    def to_dict(self) -> dict:
        """The layout kept in config/accounts.json."""
        return {"email": self.__email, "name": self.__name, "role": self.__role}

    @staticmethod
    def from_dict(data: dict) -> "Account":
        """Build an account from its saved layout. Raises ValueError if data is not an object or a value is bad."""
        if not isinstance(data, dict):
            raise ValueError("An account must be an object with an email, a name and a role.")
        return Account(data.get("email", ""), data.get("name", ""), data.get("role", Account.OFFICER))
