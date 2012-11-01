from google.appengine.ext import db

    
class Schools(db.Model):
    name = db.StringProperty()
    term = db.StringProperty()
    
    @property
    def majors(self):
        items = MajorSchool.all().filter('school =', self)
        return items.fetch(1000)
        
        
class Majors(db.Model):
    name = db.StringProperty()
    school = db.StringProperty()
    term = db.StringProperty()
    
    @property
    def courses(self):
        items = CourseMajor.all().filter('major =', self)
        return items.fetch(1000)
        
class Courses(db.Model):
    name = db.StringProperty()
    des = db.TextProperty()
    code = db.StringProperty()
    major = db.StringProperty()
    instructor = db.StringProperty()
    schedule = db.StringProperty()
    school = db.StringProperty()
    term = db.StringProperty()
    
    @property
    def time(self):
        items = Time.all().filter('course =',self)
        return items.fetch(1000)


class Time(db.Model):
    day = db.StringProperty()
    start = db.FloatProperty()
    end = db.FloatProperty()
    course = db.ReferenceProperty(Courses)

        
class MajorSchool(db.Model):
    school = db.ReferenceProperty(Schools)
    major = db.ReferenceProperty(Majors)
    
class CourseMajor(db.Model):
    major = db.ReferenceProperty(Majors)
    course = db.ReferenceProperty(Courses)
    
    
    
    
    
"""
Engl-104-M Engl for Multilingual spkers II

New

01/25/2012-05/11/2012
Course Tuesday, Thursday 08:35AM-09:50AM, MHC, Room to be announced
0.00

01/25/12
"""