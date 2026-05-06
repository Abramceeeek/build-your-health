import sys
import os
from datetime import datetime, timezone

# Add project root to python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.config import get_settings
from backend.models.database import get_session_factory, DailyTask, User
from backend.routers.tasks import _get_user_schedule
from backend.services.muscle_workout_builder import build_workout_for_day

def update():
    settings = get_settings()
    SessionLocal = get_session_factory(settings.database_url)
    db = SessionLocal()
    
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    users = db.query(User).all()
    count = 0
    
    for user in users:
        # Get all future/today uncompleted gym tasks
        tasks_to_delete = db.query(DailyTask).filter(
            DailyTask.user_id == user.id,
            DailyTask.date >= today,
            DailyTask.section == "gym",
            DailyTask.completed == False
        ).all()
        
        if not tasks_to_delete:
            continue
            
        # Group by date
        dates = set(t.date for t in tasks_to_delete)
        
        # Delete old uncompleted gym tasks
        for t in tasks_to_delete:
            db.delete(t)
            
        db.commit()
        
        # Now regenerate gym tasks for those dates
        for date_str in dates:
            day_idx = datetime.strptime(date_str, "%Y-%m-%d").weekday()
            day_types, day_focuses = _get_user_schedule(user, date_str)
            
            gym_session_idx = 0
            for i in range(day_idx):
                if day_types[i] == "gym":
                    gym_session_idx += 1
                    
            reg = user.registration_data_json or {}
            muscle_schedule = reg.get("muscle_schedule")
            
            # Find max sort_order for that day to append
            existing = db.query(DailyTask).filter(DailyTask.user_id == user.id, DailyTask.date == date_str).all()
            max_order = max((t.sort_order for t in existing), default=0) if existing else 0
            
            if muscle_schedule and str(gym_session_idx) in muscle_schedule:
                day_muscles = muscle_schedule[str(gym_session_idx)]
                gym_tasks = build_workout_for_day(db, user, date_str, day_muscles, plan_id=None)
                
                for gt in gym_tasks:
                    gt.sort_order = max_order + 1
                    max_order += 1
                    db.add(gt)
                count += 1
            else:
                # Fallback to legacy if no muscle_schedule
                from backend.routers.tasks import DEFAULT_GYM_BY_FOCUS
                focus = day_focuses[day_idx]
                gym_exercises = DEFAULT_GYM_BY_FOCUS.get(focus, DEFAULT_GYM_BY_FOCUS["Push day"])
                for item in gym_exercises:
                    title = item.get("name") or item.get("title", "")
                    desc = item.get("desc", item.get("description", ""))
                    db.add(DailyTask(
                        user_id=user.id, plan_id=None, date=date_str,
                        section="gym", task_key=item["key"], title=title,
                        description=desc, category="fitness",
                        priority=item.get("priority", False), difficulty="normal",
                        duration_minutes=item.get("dur", 0),
                        exercise_sets=item.get("sets", ""),
                        exercise_weight=item.get("weight", ""),
                        xp_reward=item.get("xp", 10), sort_order=max_order + 1
                    ))
                    max_order += 1
                count += 1

    db.commit()
    print(f"Successfully regenerated gym tasks for {count} user-days from {today} onwards.")

if __name__ == '__main__':
    update()
