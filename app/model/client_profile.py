"""ClientProfile: who the client is."""


class ClientProfile:
    """The client's name, nationality, country of residence and age."""

    MIN_AGE: int = 18
    MAX_AGE: int = 120

    def __init__(self, name: str = "", nationality: str = "", country_of_residence: str = "",
                 age: int | None = None) -> None:
        self.__check_age(age)
        self.__name: str = name
        self.__nationality: str = nationality
        self.__country_of_residence: str = country_of_residence
        self.__age: int | None = age

    @property
    def name(self) -> str:
        return self.__name

    @name.setter
    def name(self, name: str) -> None:
        self.__name = self.__text(name, "name")

    @property
    def nationality(self) -> str:
        return self.__nationality

    @nationality.setter
    def nationality(self, nationality: str) -> None:
        self.__nationality = self.__text(nationality, "nationality")

    @property
    def country_of_residence(self) -> str:
        return self.__country_of_residence

    @country_of_residence.setter
    def country_of_residence(self, country: str) -> None:
        self.__country_of_residence = self.__text(country, "country of residence")

    @property
    def age(self) -> int | None:
        return self.__age

    @age.setter
    def age(self, age: int | None) -> None:
        self.__check_age(age)
        self.__age = age

    def to_dict(self) -> dict:
        return {"name": self.__name, "nationality": self.__nationality,
                "country_of_residence": self.__country_of_residence, "age": self.__age}

    def __text(self, value: str, label: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"the client's {label} cannot be empty")
        return value.strip()

    def __check_age(self, age: int | None) -> None:
        if age is None:
            return
        if isinstance(age, bool) or not isinstance(age, int):
            raise ValueError("age must be a whole number or left empty")
        if not ClientProfile.MIN_AGE <= age <= ClientProfile.MAX_AGE:
            raise ValueError(f"age must be between {ClientProfile.MIN_AGE} and {ClientProfile.MAX_AGE}")
