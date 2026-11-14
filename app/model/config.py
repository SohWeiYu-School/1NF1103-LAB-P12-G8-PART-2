"""Config: the policy rules and the name lists, held as one plain object."""


class Config:
    """The settings every check reads: policy (thresholds, routing) and vocabulary (code names).

    Config does not read files. The Data Manager's ConfigReader reads them and App
    hands the contents in here.
    """

    def __init__(self, policy: dict, vocabulary: dict) -> None:
        self.__policy: dict = policy or {}
        self.__vocabulary: dict = vocabulary or {}

    @property
    def policy(self) -> dict:
        return self.__policy

    @property
    def vocabulary(self) -> dict:
        return self.__vocabulary

    def category_name(self, code: str) -> str:
        """'TRADE_BASED_ML' -> its readable name from the vocabulary. Unknown codes come back as given."""
        return self.__vocabulary.get("crime_categories", {}).get(code, code)

    def same_country(self, name: str) -> str:
        """Lower-case a country name and map short forms (UAE, Dubai) to one spelling."""
        text = (name or "").strip().lower()
        return self.__policy.get("country_aliases", {}).get(text, text)
