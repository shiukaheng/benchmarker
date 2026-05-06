from sqlmodel import SQLModel, Field, Session, create_engine, select


class Item(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str


engine = create_engine("sqlite:///app.db")

SQLModel.metadata.create_all(engine)

with Session(engine) as session:
    for i in range(10):
        session.add(Item(name=f"item-{i}"))

    session.commit()

with Session(engine) as session:
    items = session.exec(select(Item)).all()

    for item in items:
        print(item.id, item.name)