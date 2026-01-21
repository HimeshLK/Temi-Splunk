from sqlalchemy.orm import Session
from .models import Registration, Feedback
from .schemas import RegistrationIn, FeedbackIn

def create_registration(db: Session, event_id: str, data: RegistrationIn):
    row = Registration(event_id=event_id, name=data.name.strip(), email=str(data.email).lower(), designation=data.designation.strip())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row

def create_feedback(db: Session, event_id: str, data: FeedbackIn):
    row = Feedback(event_id=event_id, rating=str(data.rating), comment=data.comment.strip())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row

def get_registrations(db: Session, event_id: str):
    return db.query(Registration).filter(Registration.event_id == event_id).order_by(Registration.created_at.desc()).all()

def get_feedback(db: Session, event_id: str):
    return db.query(Feedback).filter(Feedback.event_id == event_id).order_by(Feedback.created_at.desc()).all()
