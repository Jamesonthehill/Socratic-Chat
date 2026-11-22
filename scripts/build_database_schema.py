"""Build editable SVG and high-resolution PNG ER diagrams from checked repository DDL.

Source: platform_app/migrations, Socratic-Chat/backend/app/db.py,
adaptive-learning-app/backend/app/db.py, reflections-app/backend/app/models.py.
"""
from pathlib import Path
import html
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "architecture-report-assets"
OUT.mkdir(parents=True, exist_ok=True)
NAVY = "#18344C"
BLUE = "#2D607F"
PALE = "#EAF2F6"
LIGHT = "#F7FAFB"
LINE = "#8CA4B5"
TEXT = "#294358"


def start(title, width=2600, height=1430):
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
         f'<rect width="{width}" height="{height}" fill="white"/>',
         f'<text x="{width/2}" y="72" text-anchor="middle" font-family="Arial" font-size="46" font-weight="700" fill="{NAVY}">{html.escape(title)}</text>']
    return s


def line(s, x1, y1, x2, y2, label="1 : N", dash=False):
    d = ' stroke-dasharray="14 9"' if dash else ""
    s.append(f'<path d="M{x1},{y1} L{x2},{y2}" fill="none" stroke="{BLUE}" stroke-width="4"{d}/>')
    if label:
        x=(x1+x2)/2; y=(y1+y2)/2-13
        s.append(f'<rect x="{x-60}" y="{y-28}" width="120" height="36" rx="8" fill="white"/>')
        s.append(f'<text x="{x}" y="{y}" text-anchor="middle" font-family="Arial" font-size="25" fill="{BLUE}">{html.escape(label)}</text>')


def path(s, points, label="1 : N", label_xy=None, dash=False):
    d=" ".join(("M" if i==0 else "L")+f"{x},{y}" for i,(x,y) in enumerate(points))
    dd=' stroke-dasharray="14 9"' if dash else ''
    s.append(f'<path d="{d}" fill="none" stroke="{BLUE}" stroke-width="4"{dd}/>')
    if label_xy:
        x,y=label_xy
        s.append(f'<rect x="{x-65}" y="{y-30}" width="130" height="40" rx="8" fill="white"/>')
        s.append(f'<text x="{x}" y="{y}" text-anchor="middle" font-family="Arial" font-size="24" fill="{BLUE}">{html.escape(label)}</text>')


def box(s,x,y,w,title,fields,subtitle=None):
    row=39; h=94+row*len(fields)+(34 if subtitle else 0)
    s.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" fill="{LIGHT}" stroke="{LINE}" stroke-width="3"/>')
    s.append(f'<path d="M{x+1},{y+16} Q{x+1},{y+1} {x+16},{y+1} H{x+w-16} Q{x+w-1},{y+1} {x+w-1},{y+16} V{y+77} H{x+1} Z" fill="{PALE}"/>')
    s.append(f'<text x="{x+24}" y="{y+51}" font-family="Arial" font-size="28" font-weight="700" fill="{NAVY}">{html.escape(title)}</text>')
    if subtitle:
        s.append(f'<text x="{x+24}" y="{y+104}" font-family="Arial" font-size="22" font-style="italic" fill="{BLUE}">{html.escape(subtitle)}</text>')
    first=y+(137 if subtitle else 111)
    for i,field in enumerate(fields):
        color=BLUE if field.startswith(('PK','FK','UQ')) else TEXT
        s.append(f'<text x="{x+24}" y="{first+i*row}" font-family="Arial" font-size="24" fill="{color}">{html.escape(field)}</text>')
    return h


def note(s,text,x=100,y=1380,size=22):
    s.append(f'<text x="{x}" y="{y}" font-family="Arial" font-size="{size}" fill="{TEXT}">{html.escape(text)}</text>')


def save(name,s):
    svg=OUT/f'{name}.svg'; svg.write_text(''.join(s)+'</svg>', encoding='utf-8')
    png=OUT/f'{name}.png'
    subprocess.run(['/opt/homebrew/bin/rsvg-convert','-w','3200','-o',str(png),str(svg)],check=True)
    print(svg)
    print(png)


# Core platform schema: solid links are declared foreign keys. Additional user
# foreign keys appear inside the child entities to keep the drawing uncluttered.
s=start('PLATFORM  |  CORE ASSIGNMENT SCHEMA', height=1500)
box(s,80,180,650,'platform.users_platform',['PK id : UUID','UQ username : TEXT','UQ email : TEXT','auth_provider : TEXT'])
box(s,980,180,650,'platform.courses_platform',['PK id : UUID','FK instructor_id → users.id','UQ (instructor_id, course_code)','title : TEXT'])
box(s,1860,180,650,'course_memberships_platform',['PK id : UUID','FK course_id → courses.id','FK user_id → users.id','UQ (course_id, user_id)','course_role / status : TEXT'])
box(s,980,650,650,'platform.assignments_platform',['PK id : UUID','FK course_id → courses.id','FK creator_id → users.id','tool / status : TEXT','config / snapshot : JSONB'])
box(s,1860,650,650,'assignment_recipients_platform',['PK (assignment_id, student_id)','FK assignment_id → assignments.id','FK student_id → users.id'])
box(s,980,1110,650,'assignment_attempts_platform',['PK id : UUID','FK assignment_id → assignments.id','FK student_id → users.id','UQ (assignment_id, student_id)','engine_state / messages / result : JSONB'])
line(s,730,310,980,310,'1 : N')
line(s,1630,310,1860,310,'1 : N')
line(s,1305,449,1305,650,'1 : N')
line(s,1630,760,1860,760,'1 : N')
line(s,1305,919,1305,1110,'1 : N')
note(s,'Declared FKs: courses.instructor_id; memberships.course_id/user_id; assignments.course_id/creator_id;',100,1420)
note(s,'recipients.assignment_id/student_id; attempts.assignment_id/student_id. Debate and AIducate use platform attempts.',100,1455)
save('database-erd-platform',s)

# Socratic and RAG: the platform assignment engine stores its active state in
# platform.assignment_attempts_platform; these are distinct supporting tables.
s=start('SOCRATIC + SHARED RAG  |  SUPPORTING SCHEMA', height=1390)
box(s,80,180,770,'platform.users / courses',['PK users.id : UUID','PK courses.id : UUID','shared identity and course scope'])
box(s,960,180,770,'conversations_socratic_chat',['PK id : UUID','FK user_id → platform.users.id','FK course_id → platform.courses.id','conversation_status / active_concept'])
box(s,1840,180,680,'conversation_messages_socratic_chat',['PK id : BIGSERIAL','FK conversation_id → conversations.id','role / content / metadata'])
box(s,80,750,770,'shared_rag.documents',['PK id : UUID','FK user_id → platform.users.id','FK course_id → platform.courses.id','FK conversation_id → socratic.conversations.id','filename / content / is_published'])
box(s,960,750,770,'shared_rag.chunks',['PK id : UUID','FK file_id → documents.id','UQ (file_id, chunk_index)','chunk_text / embedding : vector','course_id / metadata'])
box(s,1840,750,680,'learning_objectives_platform',['PK id : UUID','FK course_id → platform.courses.id','FK file_id → shared_rag.documents.id','source_chunk_ids : JSONB'])
line(s,850,310,960,310,'1 : N'); line(s,1730,310,1840,310,'1 : N')
line(s,850,900,960,900,'1 : N')
path(s,[(470,391),(470,750)],'1 : N',(470,645))
path(s,[(850,1020),(850,1170),(2180,1170),(2180,960)],'1 : N',(1500,1150))
note(s,'The current assignment tutor persists engine_state and messages in platform.assignment_attempts_platform.',100,1310)
note(s,'Socratic conversation tables and shared RAG tables are supporting records; dashed or inferred links are omitted.',100,1345)
save('database-erd-socratic-rag',s)

# SDL uses the same DDL string for PostgreSQL or SQLite; its PostgreSQL
# connection sets search_path to self_directed_learning.
s=start('SELF DIRECTED LEARNING  |  SERVICE SCHEMA', height=1510)
box(s,80,180,650,'self_directed_learning.users',['PK id : TEXT','UQ email : TEXT','role : instructor | student'])
box(s,980,180,650,'self_directed_learning.assignments',['PK id : TEXT','FK instructor_id → users.id','status / learning_plan'])
box(s,1860,180,650,'self_directed_learning.recipients',['PK (assignment_id, student_id)','FK assignment_id → assignments.id','FK student_id → users.id'])
box(s,80,680,650,'self_directed_learning.documents',['PK id : TEXT','FK assignment_id → assignments.id','filename / path'])
box(s,980,680,650,'self_directed_learning.chunks',['PK id : TEXT','FK document_id → documents.id','position / content / embedding'])
box(s,1860,680,650,'self_directed_learning.attempts',['PK id : TEXT','FK assignment_id → assignments.id','FK student_id → users.id','UQ (assignment_id, student_id)','phase / learning_state'])
box(s,980,1170,650,'self_directed_learning.messages',['PK id : TEXT','FK attempt_id → attempts.id','role / content / sources'])
box(s,1860,1170,650,'self_directed_learning.evidence',['PK id : TEXT','FK attempt_id → attempts.id','objective_id / response / score'])
line(s,730,300,980,300,'1 : N'); line(s,1630,300,1860,300,'1 : N')
line(s,730,810,980,810,'1 : N')
path(s,[(1305,448),(1305,530),(405,530),(405,680)],'1 : N',(820,505))
path(s,[(1630,370),(1750,370),(1750,450),(2185,450),(2185,680)],'1 : N',(1980,430))
path(s,[(2185,948),(2185,1085),(1305,1085),(1305,1170)],'1 : N',(1750,1060))
line(s,2185,948,2185,1170,'1 : N')
note(s,'Additional tables: lab_sessions, lab_codes, lab_enrollments. SDL users are service-local identities.',100,1470)
save('database-erd-sdl',s)

# Reflections has explicit cross-schema FKs into platform, plus LangGraph's
# checkpoint tables, whose thread correlation is application-level.
s=start('REFLECTIONS  |  SERVICE SCHEMA', height=1390)
box(s,80,170,710,'platform.users / courses',['PK users.id : UUID','PK courses.id : UUID','cross-schema identity and course'])
box(s,970,170,710,'modules_reflections_app',['PK id : TEXT','FK course_id → platform.courses.id','name / module_type'])
box(s,1840,170,710,'module_configs_reflections_app',['PK id : TEXT','FK module_id → modules.id','UQ module_id','topics / depth / milestone prompt'])
box(s,970,730,710,'conversations_reflections_app',['PK id : TEXT','FK module_id → modules.id','FK platform_user_id → platform.users.id','FK course_id → platform.courses.id','transcript / duration'])
box(s,1840,730,710,'reflection_analytics_reflections_app',['PK id : TEXT','FK conversation_id → conversations.id','UQ conversation_id','topics / scores / misconceptions'])
box(s,80,730,710,'reflections_app LangGraph checkpoints',['checkpoints_reflections_app','checkpoint_blobs_reflections_app','checkpoint_writes_reflections_app','checkpoint_migrations_reflections_app','thread_id / checkpoint_id : service-managed'])
line(s,790,300,970,300,'1 : N'); line(s,1680,300,1840,300,'1 : 1')
line(s,1325,438,1325,730,'1 : N'); line(s,1680,860,1840,860,'1 : 0..1')
path(s,[(790,860),(970,860)],'logical',(880,830),True)
note(s,'Legacy students_reflections_app may link to conversations; platform sessions use platform_user_id.',100,1310)
note(s,'Dashed checkpoint link is application-level correlation, not a declared SQL foreign key.',100,1345)
save('database-erd-reflections',s)

# Single high-resolution reference sheet for review and presentation.
from PIL import Image

sheet = Image.new('RGB', (6600, 4000), 'white')
for name, xy in [
    ('platform', (50, 60)), ('socratic-rag', (3350, 60)),
    ('sdl', (50, 2050)), ('reflections', (3350, 2050)),
]:
    panel = Image.open(OUT / f'database-erd-{name}.png').convert('RGB')
    sheet.paste(panel, xy)
combined = ROOT / 'docs' / 'Combined-Database-Schema.png'
sheet.save(combined, optimize=True)
print(combined)
