import {useNavigate} from "react-router-dom";
import LessonWorkspace from "../../self-directed-learning/student-app/src/LessonWorkspace";
import {configureStudentTransport} from "../../self-directed-learning/student-app/src/api";
import {studentTransport} from "./self-directed-api";
import "./sdl-teaching-ui.css";

configureStudentTransport(studentTransport);

export default function SDLWorkspace({assignmentId}) {
  const navigate=useNavigate();
  return <div className="sdl-teaching-ui sdl-student-ui"><div className="platform-sdl"><LessonWorkspace assignmentId={assignmentId} onBack={()=>navigate("/student")} embedded/></div></div>;
}
