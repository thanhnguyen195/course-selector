#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import webapp2
import jinja2
import os
import string
import re

from google.appengine.ext import db
from google.appengine.ext import webapp
from django.utils import simplejson
from google.appengine.api import urlfetch

import data

################################################################################
################ Template create part ######################

template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_environment = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir),
                                        autoescape = True)
                                        
def render_template(template, **params):
    template = jinja_environment.get_template(template)
    return template.render(params)
    
class BaseHandler(webapp2.RequestHandler):
    def write(self, *a, **kw):
        self.response.out.write(*a, **kw)
        
    def render_template(self, template, **params):
        return render_template(template, **params)
        
    def render(self, template, **kw):
        self.write(self.render_template(template, **kw))
        
###############################################################################

class MainHandler(BaseHandler):
    def get(self):
        schools = data.Schools.all().fetch(10)
        currentschool = self.request.get("school")
        majors = data.Majors.all().filter('school =',currentschool).fetch(1000)
        currentmajor = self.request.get("major")
        courses = data.Courses.all().filter('school =',currentschool).filter('major =',currentmajor).fetch(1000)
        self.render("search.html", schools = schools, majors = majors, courses = courses)
        
class InputData(BaseHandler):

    def get(self):
        self.render("inputdata.html")

    def post(self):
        def convert_time(time): # convert a token in form of "10:00AM" to a float number represent for it in the 24 hour form
            hour = float(time[:2])
            minute = float(time[3:5])
            if time[5]=="A":
                result = hour + minute/60
            elif time[5]=="P":
                result = hour + float(12) + minute/60
            return result

        def split_data(data): # convert a token in form of "MWF 10:00AM-10:50AM" to list of day and two float number represent the start and end time of the class
            day_token = data[:data.index(" ")] # e.g: "MFW"
            time_token = data[data.index(" ")+1:] # e.g "10:00AM-01:00PM"
            days = re.findall(r"(?:[T][H])|[M]|[T]|[W]|[F]|[S]",day_token)
            time_tokens = re.findall(r"[0-9][0-9][:][0-9][0-9][A|P][M]",time_token) # e.g "10:00AM"
            start = convert_time(time_tokens[0])
            end = convert_time(time_tokens[1])
            return days, start, end
                    
        #@db.transactional(xg=True) #put this thing went deploy to test if the atomic function work properly
        def put_data():
            name = self.request.get('name')
            des = self.request.get('des')
            code = self.request.get('code')
            instructor = self.request.get('instructor')
            time = self.request.get('time')
            major = self.request.get('major')
            school = self.request.get('school')
            term = self.request.get('term')
            name, des, code, instructor, time, major, school, term = name.strip(), des.strip(), code.strip(), instructor.strip(), time.strip(), major.strip(), school.strip(), term.strip()
        
            coursedata = data.Courses(name = name,
                             des = des,
                             code = code,
                             instructor = instructor,
                             time = time,
                             major = major,
                             school = school,
                             term = term)
            coursedata.put()
            majordata = data.Majors.get_or_insert(major,
                           name = major,
                           school = school,
                           term = term)
            majordata.put()
            coursemajor = data.CourseMajor(major = majordata, course = coursedata)
            coursemajor.put()
            
            schooldata = data.Schools.get_or_insert(school,
                                  name = school,
                                  term = term)
            schooldata.put()
            majorschool = data.MajorSchool.get_or_insert(schooldata.name+majordata.name,school = schooldata, major = majordata)
            majorschool.put()
            #convert the time of the schedule to the Time class
            time_tokens = re.findall(r"[A-Z]+[ ][0-9][0-9][:][0-9][0-9][A|P][M][-][0-9][0-9][:][0-9][0-9][A|P][M]",time) 
            for token in time_tokens:
                days, start, end = split_data(token)
                for day in days:
                    time = data.Time(day = day, start = start, end = end, course = coursedata)
                    time.put()
            self.redirect('/inputdata')
        put_data()

class UserSchedule(BaseHandler):
    def get(self):
        courses = data.Courses.all().fetch(1000)
        self.render("userschedule.html", courses=courses)



class URLFetchHandler(BaseHandler):
    def get(self):
        
        
        #########               Smith time process path         ######################
        
        def convert_time_Smith(time): # convert a token in form of "10:00" to a float number represent for it in the 24 hour form
            hour = float(time[:2])
            minute = float(time[3:5])
            if hour>7:
                result = hour + minute/60
            elif hour<8:
                result = hour + float(12) + minute/60
            return result
        
        def split_data_Smith(data):
            day_token = data[:data.index(" ")] # e.g: "MFW"
            time_token = data[data.index(" ")+1:] # e.g "10:00-01:00"
            days = re.findall(r"(?:[T][h])|[M]|[T]|[W]|[F]|[S]",day_token)
            time_tokens = re.findall(r"[0-9][0-9][:][0-9][0-9]",time_token) # e.g "10:00"
            start = convert_time_Smith(time_tokens[0])
            end = convert_time_Smith(time_tokens[1])
            final_days=[]
            for day in days:
                if day=="M":
                    final_days.append(2)
                if day=="T":
                    final_days.append(3)
                if day=="W":
                    final_days.append(4)
                if day=="Th":
                    final_days.append(5)
                if day=="F":
                    final_days.append(6)
                if day=="S":
                    final_days.append(7)
            return final_days, start, end
        
        def SmithTimeProcess(content):
            courseDays=[]
            courseStarts=[]
            courseEnds=[]
            time_tokens = re.findall(r"[A-Z|a-z]+[ ][0-9][0-9][:][0-9][0-9][-][0-9][0-9][:][0-9][0-9]",content) #TTh 10:30-11:50
            for token in time_tokens:
                days, start, end = split_data_Smith(token)
                for day in days:
                    courseDays.append(day)
                    courseStarts.append(start)
                    courseEnds.append(end)
            return courseDays,courseStarts,courseEnds
        
        ############################################################################
        
        
        
        #########               Hampshire time process path         ######################
        
        def convert_time_Hampshire(time): # convert a token in form of "10:00" to a float number represent for it in the 24 hour form
            hour = float(time[:2])
            minute = float(time[3:5])
            if time[5]=="A":
                result = hour + minute/60
            elif time[5]=="P":
                result = hour + float(12) + minute/60
            return result
        
        def split_data_Hampshire(data):
            time_token = data[:data.index(" ")]  # e.g "10:00-01:00"
            day_token = data[data.index(" ")+1:] # e.g: "MFW"
            days = re.findall(r"(?:[T][H])|[M]|[T]|[W]|[F]|[S]",day_token)
            time_tokens = re.findall(r"[0-9][0-9][:][0-9][0-9][A|P][M]",time_token) # e.g "10:00AM"
            #return time_tokens,1,1
            start = convert_time_Hampshire(time_tokens[0])
            end = convert_time_Hampshire(time_tokens[1])
            final_days=[]
            for day in days:
                if day=="M":
                    final_days.append(2)
                if day=="T":
                    final_days.append(3)
                if day=="W":
                    final_days.append(4)
                if day=="TH":
                    final_days.append(5)
                if day=="F":
                    final_days.append(6)
                if day=="S":
                    final_days.append(7)
            return final_days, start, end
        
        def HampshireTimeProcess(content):
            courseDays=[]
            courseStarts=[]
            courseEnds=[]
            time_tokens = re.findall(r"[0-9][0-9][:][0-9][0-9][A|P][M][-][0-9][0-9][:][0-9][0-9][A|P][M][ ][A-Z|a-z|,]+",content) #10:30AM-11:50AM T,TH
            for token in time_tokens:
                days, start, end = split_data_Hampshire(token)
                for day in days:
                    courseDays.append(day)
                    courseStarts.append(start)
                    courseEnds.append(end)
            return courseStarts,courseStarts,courseEnds
        
        ############################################################################
        
        
        #########               Mount Holyoke College time process path         ######################
        
        def convert_time_Moho(time): # convert a token in form of "10:00" to a float number represent for it in the 24 hour form
            hour = float(time[:2])
            minute = float(time[3:5])
            if time[5]=="A":
                result = hour + minute/60
            elif time[5]=="P":
                result = hour + float(12) + minute/60
            return result
        
        def split_data_Moho(data):
            day_token = data[:data.index(" ")]
            time_token = data[data.index(" ")+1:] 
            days = re.findall(r"(?:[T][H])|[M]|[T]|[W]|[F]|[S]",day_token)
            time_tokens = re.findall(r"[0-9][0-9][:][0-9][0-9][A|P][M]",time_token) # e.g "10:00AM"
            #return time_tokens,1,1
            start = convert_time_Moho(time_tokens[0])
            end = convert_time_Moho(time_tokens[1])
            final_days=[]
            for day in days:
                if day=="M":
                    final_days.append(2)
                if day=="T":
                    final_days.append(3)
                if day=="W":
                    final_days.append(4)
                if day=="TH":
                    final_days.append(5)
                if day=="F":
                    final_days.append(6)
                if day=="S":
                    final_days.append(7)
            return final_days, start, end
        
        def MohoTimeProcess(content):
            courseDays=[]
            courseStarts=[]
            courseEnds=[]
            time_tokens = re.findall(r"[A-Z|a-z|,]+[ ][0-9][0-9][:][0-9][0-9][A|P][M][-][0-9][0-9][:][0-9][0-9][A|P][M]",content) #MW 11:00AM-12:15PM;F 11:00AM-11:50AM
            #return time_tokens
            for token in time_tokens:
                days, start, end = split_data_Moho(token)
                for day in days:
                    courseDays.append(day)
                    courseStarts.append(start)
                    courseEnds.append(end)
            return courseDays,courseStarts,courseEnds
        
        ############################################################################
        
        
        #########          University of Massachusett at Amherst time process path         ######################
        
        def convert_time_UMass(time): # convert a token in form of "10:00" to a float number represent for it in the 24 hour form
            if len(time)==6:
                time="0"+time
            hour = float(time[:2])
            minute = float(time[3:5])
            if time[5]=="A":
                result = hour + minute/60
            elif time[5]=="P":
                result = hour + float(12) + minute/60
            return result
        
        def split_data_UMass(data):
            time_to_find = re.findall(r"[0-9]+[:][0-9][0-9]",data)
            index = data.index(time_to_find[0])-1
            day_token = data[:index]
            time_token = data[index+1:]
            days = re.findall(r"(?:[T][H])|[M]|(?:[T][U])|[W]|[F]|[S]",day_token)
            time_tokens = re.findall(r"[0-9]+[:][0-9][0-9][A|P][M]",time_token) # e.g "10:00AM"
            #return time_tokens,1,1
            start = convert_time_UMass(time_tokens[0])
            end = convert_time_UMass(time_tokens[1])
            final_days=[]
            for day in days:
                if day=="M":
                    final_days.append(2)
                if day=="TU":
                    final_days.append(3)
                if day=="W":
                    final_days.append(4)
                if day=="TH":
                    final_days.append(5)
                if day=="F":
                    final_days.append(6)
                if day=="S":
                    final_days.append(7)
            return final_days, start, end
        
        def UMassTimeProcess(content):
            courseDays=[]
            courseStarts=[]
            courseEnds=[]
            time_tokens = re.findall(r"(?:[A-Z]+[ ])+[0-9]+[:][0-9][0-9][A|P][M][ ][0-9]+[:][0-9][0-9][A|P][M]",content) #TU TH 1:00PM 2:15PM
            #return time_tokens
            for token in time_tokens:
                days, start, end = split_data_UMass(token)
                for day in days:
                    courseDays.append(day)
                    courseStarts.append(start)
                    courseEnds.append(end)
            return courseDays,courseStarts,courseEnds
        
        ############################################################################
        
        
        def coursePageProcess(link,sect):
            page = urlfetch.fetch(link)
            if page.status_code == 200:
                content = page.content
                start = content.find("</head>")
                content = content[start:]
                
                start = content.find("> -->")+5
                end = content.find("<!--",start)
                courseTitle = content[start:end].strip()
                
                start = content.find("field field-name-field-course-semester field-type-list-text field-label-inline clearfix")
                end = content.find("field field-name-field-course-year field-type-list-text field-label-inline clearfix")
                token = content[start:end].strip()
                start = token.find("field-item even")+17
                end = token.find("</div>",start)
                courseSemester = token[start:end]
                
                start = content.find("field field-name-field-course-year field-type-list-text field-label-inline clearfix")
                end = content.find("field field-name-field-course-subject-name field-type-text field-label-inline clearfix")
                token = content[start:end].strip()
                start = token.find("field-item even")+17
                end = token.find("</div>",start)
                courseYear = token[start:end]
                
                start = content.find("field field-name-field-course-subject-name field-type-text field-label-inline clearfix")
                end = content.find("field field-name-field-course-number field-type-text field-label-inline clearfix")
                token = content[start:end].strip()
                start = token.find("field-item even")+17
                end = token.find("</div>",start)
                courseSubject = token[start:end]
                
                start = content.find("field field-name-field-course-institution field-type-list-text field-label-inline clearfix")
                end = content.find("field field-name-body field-type-text-with-summary field-label-hidden")
                token = content[start:end].strip()
                start = token.find("field-item even")+17
                end = token.find("</div>",start)
                courseSchool = token[start:end]
                
                start = content.find("field field-name-body field-type-text-with-summary field-label-hidden")
                end = content.find("field field-name-field-course-comments field-type-text-long field-label-inline clearfix")
                token = content[start:end].strip()
                start = token.find("content:encoded")+17
                end = token.find("</div>",start)
                courseDescription = token[start:end]
                
                start = content.find("field field-name-field-course-comments field-type-text-long field-label-inline clearfix")
                end = content.find("field field-name-field-course-linked field-type-list-boolean field-label-inline clearfix")
                token = content[start:end].strip()
                start = token.find("field-item even")+17
                end = token.find("</div>",start)
                courseNote = token[start:end]
                
                start = content.find("field field-name-field-course-linked field-type-list-boolean field-label-inline clearfix")
                end = content.find("field field-name-field-course-instructor-perm field-type-list-boolean field-label-inline clearfix")
                token = content[start:end].strip()
                start = token.find("field-item even")+17
                end = token.find("</div>",start)
                courseLink = token[start:end]
                
                start = content.find("field field-name-field-course-instructor-perm field-type-list-boolean field-label-inline clearfix")
                end = content.find("field field-name-field-course-url field-type-link-field field-label-inline clearfix")
                token = content[start:end].strip()
                start = token.find("field-item even")+17
                end = token.find("</div>",start)
                courseInsPer = token[start:end]
                
                ############### take the time out aka the hardest part ################
                start = content.find("summary=\"Five College Course Schedule")
                end = content.find("</table>",start)
                table = content[start:end]
                start = table.find("<tbody>")
                end = table.find("</tbody>")
                tbody = table[start:end]
                
                while (tbody.find("<tr")!=-1):
                    start = tbody.find("<tr")
                    end = tbody.find("</tr>")
                    token = tbody[start:end]
                    
                    start = token.find("course-section-number views-align-left")+41
                    end = token.find("</td>",start)
                    section = token[start:end].strip()
                    if (section==sect):
                        break
                    tbody = tbody[end+5:]
                
                start = token.find("course-credits")+17
                end = token.find("</td>",start)
                courseCredit = token[start:end].strip()
                
                start = token.find("course-instructor")+20
                end = token.find("</td>",start)
                courseInstructor = token[start:end].strip()
                
                start = token.find("course-location")+18
                end = token.find("</td>",start)
                courseLocation = token[start:end].strip()
                
                start = token.find("course-meeting-info")+22
                end = token.find("</td>",start)
                courseTime = token[start:end].strip()
                
                
                ##### Now process the time info base on the school with different function ####
                if courseSchool=="Smith College":
                    courseDays,courseStarts,courseEnds = SmithTimeProcess(courseTime)
                    #return courseDays
                
                elif courseSchool=="Hampshire College":
                    courseDays,courseStarts,courseEnds = HampshireTimeProcess(courseTime)
                    #return courseDays
            
                elif courseSchool=="Mount Holyoke College":
                    courseDays,courseStarts,courseEnds = MohoTimeProcess(courseTime)
                    #return courseDays
                
                elif courseSchool=="Amherst College":
                    courseDays,courseStarts,courseEnds = MohoTimeProcess(courseTime)
                    #return courseDays
                
                elif courseSchool=="UMass Amherst":
                    courseDays,courseStarts,courseEnds = UMassTimeProcess(courseTime)
                    #return courseDays
                

                ###############################################################################
                #return courseTime
                
                ############ Put the data into datastore #######################
                
                
                ################################################################
                
            return "doneCoursePageProcess"
        
        def pageListProcess(content):
            start = content.find("<tbody>")
            end = content.find("</tbody>")
            tbody = content[start:end]
            
            #split tbody into courses
            courses=[]
            while (tbody.find("<tr")!=-1):
                start = tbody.find("<tr")
                end = tbody.find("</tr")
                courses.append(tbody[start:end])
                tbody = tbody[(end+5):]
            
            #split course div into courseCode, courseSection and courseLink
            courseCode=[]
            courseLink=[]
            courseSection=[]
            for course in courses:
                start = course.find("course-subject")+17
                end = course.find("</td>")
                courseSubject = course[start:end].strip()
                course = course[end+5:]
                
                start = course.find("course-number")+16
                end = course.find("</td>")
                courseNumber = course[start:end].strip()
                course = course[end+5:]
                courseCode.append(courseSubject+" "+courseNumber)
                
                start = course.find("section-number")+17
                end = course.find("</td>")
                courseSection.append(course[start:end].strip())
                
                start = course.find("<a href=")+9
                end = course.find(">",start)-1
                courseLink.append("https://www.fivecolleges.edu"+course[start:end].strip())
                
            result = coursePageProcess(courseLink[24],courseSection[24])
            #return courseLink[24]
            return result
    
        def mainFetch():
            url = "https://www.fivecolleges.edu/courses?field_course_semester_value=F&field_course_year_value=2012&field_course_institution_value=U&title=&course_instructor=&body_value=&field_course_number_value=&field_course_subject_name_value=&field_course_subject_value="
            result = urlfetch.fetch(url)
            if result.status_code == 200:
                result_display = pageListProcess(result.content)
                self.response.out.write(result_display)
        mainFetch()

app = webapp2.WSGIApplication([('/', MainHandler),
                               ('/schedule', UserSchedule),
                               ('/inputdata', InputData),
                               ('/URLFetch', URLFetchHandler)],
                              debug=True)
