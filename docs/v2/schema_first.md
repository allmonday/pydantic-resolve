# Define the Model First, Then Describe the Retrieval Method

Using pydantic-resolve's recommended approach, first define the model. Attach all operations to the defined data object.

When constructing data, a straightforward way to think is: first define the target data structure Target, compare it with the existing data source structure Source, and find the shortest path of changes.

> More detailed content will be introduced in "ERD Driven Development".

For example, I have an array of Persons, and now I want to add leave information for each person. The existing leave data in the database includes annual leave and sick leave. These need to be combined into one type.

## Expected Structure

The expected data structure includes `Person` and the corresponding `absenses`. `Absense` is a business-oriented data structure.

```python
class Person(BaseModel):
    id: int
    name: str
    absenses: List[Absense]

class Absense(BaseModel):
    type: Literal['annual', 'sick']
    start_date: date
    end_date: date
```

## Adding Data Sources

AnnualLeave and SickLeave are existing data types.

They are provided by AnnualLeaveLoader and SickLeaveLoader respectively.

```python
class AnnualLeave(BaseModel):
    person_id: int
    start_date: date
    end_date: date

class SickLeave(BaseModel):
    person_id: int
    start_date: date
    end_date: date
```

At this point, we can combine the source data and the expected data, listing the data to be retrieved and the results to be calculated.

This represents the starting data and the target data.

Using `exclude=True` can hide temporary variables in the final output.

```python
@model_config()
class Person(BaseModel):
    id: int
    name: str

    annual_leaves: List[AnnualLeave] = Field(default_factory=list, exclude=True)
    sick_leaves: List[SickLeave] = Field(default_factory=list, exclude=True)

    absenses: List[Absense] = []
```

## Loading Data

Then we add resolve and dataloader for `annual_leaves` and `sick_leaves`, which will provide data for the starting data.

```python
@model_config()
class Person(BaseModel):
    id: int
    name: str

    annual_leaves: List[AnnualLeave] = Field(default_factory=list, exclude=True)
    def resolve_annual_leaves(self, loader=LoaderDepend(AnnualLeaveLoader)):
        return loader.load(self.id)

    sick_leaves: List[SickLeave] = Field(default_factory=list, exclude=True)
    def resolve_sick_leaves(self, loader=LoaderDepend(SickLeaveLoader)):
        return loader.load(self.id)

    absense: List[Absense] = []
```

## Transforming Data

When the resolve phase of `annual_leaves` and `sick_leaves` ends, they already have actual data. Next, use the post phase to calculate `absenses`.

```python
@model_config()
class Person(BaseModel):
    id: int
    name: str

    annual_leaves: List[AnnualLeave] = Field(default_factory=list, exclude=True)
    def resolve_annual_leaves(self, loader=LoaderDepend(AnnualLeaveLoader)):
        return loader.load(self.id)

    sick_leaves: List[SickLeave] = Field(default_factory=list, exclude=True)
    def resolve_sick_leaves(self, loader=LoaderDepend(SickLeaveLoader)):
        return loader.load(self.id)

    absenses: List[Absense] = []
    def post_absense(self):
        a = [Absense(
                type='annual',
                start_date=a.start_date,
                end_date=a.end_date) for a in self.annual_leaves]
        b = [Absense(
                type='sick',
                start_date=s.start_date,
                end_date=s.end_date) for a in self.sick_leaves]
        return a + b
```

## Starting the Whole Process

After defining the complete structure of `Person` and `Absense`, we can load and calculate all data by initializing `people`. Just execute `Resolver().resolve()` on the `people` data once to complete all operations.

```python
people = [Person(id=1, name='alice'), Person(id=2, name='bob')]
people = await Resolver().resolve(people)
```

Throughout this entire assembly process, we did not write a single line of code to expand the `people` loop. All related code is inside the `Person` object.

If we were to handle this in a procedural way, we would need to at least consider:

- Aggregating annual and sick leaves based on `person_id`, generating two new variables `person_annual_map` and `person_sick_map`
- Iterating over `person` objects with `for person in people`

These processes are all encapsulated internally in pydantic-resolve.
