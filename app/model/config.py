"""Config: the policy rules, the name lists and the accounts, held as one plain object."""

from app.model.account import Account


class Config:
    """The settings every check reads: policy (thresholds, routing), vocabulary (code names) and the
    accounts that can sign in.

    Config does not read files. The Data Manager's ConfigReader reads them and App
    hands the contents in here.
    """

    def __init__(self, policy: dict | None = None, vocabulary: dict | None = None,
                 accounts: list[Account] | None = None) -> None:
        self.__policy: dict = policy or {}
        self.__vocabulary: dict = vocabulary or {}
        self.__accounts: list[Account] = list(accounts or [])

    @property
    def policy(self) -> dict:
        return self.__policy

    @property
    def vocabulary(self) -> dict:
        return self.__vocabulary

    @property
    def accounts(self) -> list[Account]:
        return self.__accounts

    def account(self, email: str) -> Account | None:
        """The account with this email (upper and lower case are treated the same), or None."""
        wanted = str(email or "").strip().lower()
        for account in self.__accounts:
            if account.email == wanted:
                return account
        return None

    def category_name(self, code: str) -> str:
        """'TRADE_BASED_ML' -> its readable name from the vocabulary. Unknown codes come back as given."""
        return self.__vocabulary.get("crime_categories", {}).get(code, code)

    def same_country(self, name: str) -> str:
        """Lower-case a country name and map short forms (UAE, Dubai) to one spelling."""
        text = (name or "").strip().lower()
        return self.__policy.get("country_aliases", {}).get(text, text)

    def asset_category(self, asset_type: str) -> str:
        """property / listed_equities / private_business / other, by the policy's keyword lists."""
        text = (asset_type or "").lower()
        for category, keywords in self.__policy["asset_categories"].items():
            if any(word in text for word in keywords):
                return category
        return "other"
