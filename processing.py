from functools import lru_cache
import requests
import json
from bs4 import BeautifulSoup
import re
from gpt import summarize


# ex: getProf("ecse-324")
@lru_cache
def getProf(courseCode, season):
    season = season.strip().lower().capitalize()

    URL = "https://www.mcgill.ca/study/2024-2025/courses/" + courseCode
    page = requests.get(URL)
    soup = BeautifulSoup(page.content, 'html.parser')
    elements = soup.find_all(class_="catalog-instructors")

    pattern = r"([\w\s',;]+)\((Fall|Winter)\)"
    matches = re.findall(pattern, str(elements))

    instructorDict = {"Fall": [], "Winter": []}

    for instructors, semester in matches:
        instructorList = instructors.split(";")
        for i in range(len(instructorList)):
            instructorList[i] = instructorList[i].strip()
        instructorDict[semester] = instructorList

    return instructorDict[season]


@lru_cache
def getProfId(name):
    URL = "https://www.ratemyprofessors.com/search/professors/1439?q=" + name
    page = requests.get(URL)
    pattern = r'"legacyId":(\d+)'
    match = re.search(pattern, page.text)
    if match:
        legacyId = match.group(1)
        return legacyId
    else:
        return "000000"


# Returns a list of dict including class, quality rating, difficulty rating, comment
@lru_cache
def getProfInfo(legacyId):
    infoList = []

    URL = "https://www.ratemyprofessors.com/professor/" + legacyId
    page = requests.get(URL)

    soup = BeautifulSoup(page.content, 'html.parser')
    elements = soup.find_all(class_="Rating__RatingBody-sc-1rhvpxz-0 dGrvXb")

    for element in elements:

        infoDict = {}

        pattern = r'RatingHeader__StyledClass-sc-1dlkqw1-3 eXfReS"> <!-- -->([^<]+)'
        match = re.search(pattern, str(element))
        if match:
            course = match.group(1)
            infoDict["course"] = course

        pattern = r'Quality.*?(\d\.\d)'
        match = re.search(pattern, str(element))
        if match:
            quality = match.group(1)
            infoDict["quality"] = quality

        pattern = r'Difficulty.*?(\d\.\d)'
        match = re.search(pattern, str(element))
        if match:
            difficulty = match.group(1)
            infoDict["difficulty"] = difficulty

        pattern = r'Comments__.*?>([^<]+)'
        match = re.search(pattern, str(element))
        if match:
            comment = match.group(1)
            infoDict["comment"] = comment.strip()

        infoList.append(infoDict)

    return infoList


def convertGradeToNumber(grade):
    if grade == "A":
        return 0
    elif grade == "A-":
        return 1
    elif grade == "B+":
        return 2
    elif grade == "B":
        return 3
    elif grade == "B-":
        return 4
    elif grade == "C+":
        return 5
    elif grade == "C":
        return 6
    elif grade == "D":
        return 7
    elif grade == "F":
        return 8
    else:
        raise ValueError("Invalid grade entered")


def convertNumberToGrade(number):
    number = round(number)
    if number == 0:
        return "A"
    elif number == 1:
        return "A-"
    elif number == 2:
        return "B+"
    elif number == 3:
        return "B"
    elif number == 4:
        return "B-"
    elif number == 5:
        return "C+"
    elif number == 6:
        return "C"
    elif number == 7:
        return "D"
    elif number == 8:
        return "F"
    else:
        raise ValueError("Invalid number entered")


def getComments(listOfClasses, semester):
    toReturn = []

    for aClass in listOfClasses:

        commentList = []

        profList = getProf(aClass, semester)

        aClass = aClass.upper().replace("-", "")

        if len(profList) >= 1:
            for prof in profList:
                infoList = getProfInfo(getProfId(prof))
                for infoDict in infoList:
                    if infoDict.get("course") == aClass:
                        commentList.append(infoDict.get("comment"))

        toReturn.append(commentList)

    return toReturn


def getAverageForClass(className):
    jsonfile = open("./data/averages.json")
    classes = json.load(jsonfile)
    jsonfile.close()
    processedName = className.upper().replace("-", "")
    grades = []
    for term in classes[processedName]:
        grades.append(term["average"])

    if len(grades) > 5:
        grades = grades[-5:]

    for i, grade in enumerate(grades):
        grades[i] = convertGradeToNumber(grade)

    average = sum(grades) / len(grades)
    lettergrade = convertNumberToGrade(average)
    return lettergrade, average


def getCreditsForClass(className):
    jsonfile = open("./data/averages.json")
    classes = json.load(jsonfile)
    jsonfile.close()
    processedName = className.upper().replace("-", "").replace(" ", "")
    try:
        return classes[processedName][-1]["credits"]
    except Exception as e:
        return 0

def classesValidation(userInput):
    jsonfile = open("./data/averages.json")
    classes = json.load(jsonfile)
    jsonfile.close()
    enteredCourses = []
    print(userInput)
    for course in userInput:
        processedName = course.upper().replace("-", "").replace(" ", "")
        try:
            classes[processedName][-1]["credits"]
        except Exception as e:
            return course + " is not a valid course"
        if course in enteredCourses:
            return course + " is a duplicated course"
        enteredCourses.append(course)
    return ""


# The higher the rating, the harder the class
def getClassRating(credit, pastAverage, classDifficulty, profRating):
    classRating = 0

    if pastAverage == "A":  # A
        classRating += 0
    elif pastAverage == "A-":  # A-
        classRating += 13
    elif pastAverage == "B+":  # B+
        classRating += 27.5
    elif pastAverage == "B":  # B
        classRating += 35
    elif pastAverage == "B-":  # B-
        classRating += 42
    elif pastAverage == "C+":  # C+
        classRating += 47
    else:
        classRating += 55

    classRating += (classDifficulty / 6) * 35

    classRating += ((6 - profRating) / 6) * 10

    if credit == 1:
        classRating *= 0.4
    elif credit == 3:
        pass
    elif credit == 4:
        classRating *= 1.2

    return classRating


# The higher the rating, the harder the semester, average is 1
def getSemesterRating(classRating, totalCredits):
    maxRating = 50 * 5

    semesterRating = 0

    for rating in classRating:
        semesterRating += rating
    multiplier = 1 + 0.05 * (totalCredits - totalCredits % 3 - 15) + 0.02 * (totalCredits % 3)
    semesterRating *= multiplier

    semesterRating /= maxRating

    return semesterRating


def getListOfClasses(classes):
    #print(userInput)
    print(type(classes))
    print(classes)
    classes = classes.split(",")
    print(classes)
    output =[]
    for i in range(len(classes)):   
        print(classes[i].strip().lower().replace(" ", "-"))

        output.append(classes[i].strip().lower().replace(" ", "-"))
    return output


def getClassDifficulty(course, season):
    classDifficulty = 0
    count = 1

    profList = getProf(course, season)

    course = course.upper().replace("-", "")

    if len(profList) >= 1:
        for prof in profList:
            infoList = getProfInfo(getProfId(prof))
            count = len(infoList)
            if count == 0:
                count = 1
            for infoDict in infoList:
                if infoDict.get("course") == course:
                    classDifficulty += float(infoDict.get("difficulty"))
    return classDifficulty / count


def getProfRating(course, season):
    profRating = 0
    count = 1

    profList = getProf(course, season)

    course = course.upper().replace("-", "")

    if len(profList) >= 1:
        for prof in profList:
            infoList = getProfInfo(getProfId(prof))
            count = len(infoList)
            if count == 0:
                count = 1
            for infoDict in infoList:
                if infoDict.get("course") == course:
                    profRating += float(infoDict.get("quality"))
    return profRating / count


def passCourseRating(course, selected_semester):
    return getClassRating(getCreditsForClass(course),
                          getAverageForClass(course)[0],
                          getClassDifficulty(course, selected_semester),
                          getProfRating(course, selected_semester))


def passSemesterRating(userInput, selected_semester):
    userInput = getListOfClasses(userInput)

    totalCredit = 0
    classRatings = []

    for course in userInput:
        totalCredit += float(getCreditsForClass(course))
        classRating = getClassRating(getCreditsForClass(course),
                                     getAverageForClass(course)[0],
                                     getClassDifficulty(course, selected_semester),
                                     getProfRating(course, selected_semester))
        classRatings.append(classRating)

    return getSemesterRating(classRatings, totalCredit)


def processUserInput(userInput, selected_semester):
    courses = []
    # comments = getComments(userInput)   # I think we need to summarize? dunno. LEL
    for i, course in enumerate(userInput):
        prof = getProf(course, selected_semester)  # To make dynamic later
        if not prof:
            prof = ['N/A']
        tmp = {
            "code": course.upper().replace("-", " "),
            "professor": prof,
            "overallDifficulty": passCourseRating(course, selected_semester),
            "comments": "TODO"
        }

        courses.append(tmp)
    return courses


def outputClasses(courses, semester):
    courses = getListOfClasses(courses)
    #print(courses)
    error = classesValidation(courses)
    if classesValidation(courses)!="":
        return error
    print("REACHED")
    outputList = []
    classRatingList = []
    profList = []
    avgList = []
    for course in courses:
        classRatingList.append(passCourseRating(course, semester))
        profList.append(getProf(course, semester))
        avgList.append(getAverageForClass(course)[0])
    
    generatedComments = summarize(getComments(courses, semester))
    
    for i in range(len(generatedComments)):
        print(profList[i])
        professorList = ", ".join(profList[i])
        singleClass = {
            "code": courses[i],
            "professor": professorList,
            "overallDifficulty": avgList[i],
            "classRating": int(classRatingList[i]),
            "comments": generatedComments[i]
        }
        outputList.append(singleClass)
    return outputList




if __name__ == "__main__":
    # avg = getClassRating(3, 3, 3, 3)
    # class1 = getClassRating(4, 3, 3, 3)
    # class2 = getClassRating(1, 1, 2, 4)
    # print(class2)
    # print(getSemesterRating([50,50,50,50, 20],13))
    # print(getSemesterRating([class1,avg,avg,avg,avg, class2],16))
    #print(summarize(getComments(["ecse-324", "ecse-325", "ecse-206", "ecse-250"], "Fall")))
    print(passCourseRating("ecse-324", "Winter"))
    print(passSemesterRating(["ecse-324", "ecse-325", "ecse-222"], "Fall"))
    print(classesValidation(["ecse-324", "ecse-324", "ecse-325", "ecse-222"]))
