from sqlmodel import SQLModel, Field, Session, create_engine, select


class Dataset(SQLModel, table=True):
    path: str = Field(primary_key=True)

engine = create_engine("sqlite:///app.db")

SQLModel.metadata.create_all(engine)

with Session(engine) as session:
    for i in range(10):
        session.add(Dataset(path=f"{i}.zip"))
    session.commit()

with Session(engine) as session:
    items = session.exec(select(Dataset)).all()
    for item in items:
        print(item.path)