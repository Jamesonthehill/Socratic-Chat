import axios from 'axios'

const SERVER_URL = import.meta.env.VITE_SERVER_URL
const backendBaseUrl = SERVER_URL

// Axios instance
const axiosInstance = axios.create({
  baseURL: backendBaseUrl,
  headers: {
    'Content-Type': 'application/json',
  },
})

export const getQuestionsByUser = async (user_id) => {
  const response = await axiosInstance.get(`/api/v1/question/user/${user_id}`)
  return response.data
}

export const getQuestionsBySession = async (session_id) => {
  const response = await axiosInstance.get(`/api/v1/question/session/${session_id}`)
  return response.data
}

export const getQuestionById = async (id) => {
  const response = await axiosInstance.get(`/api/v1/question/${id}`)
  return response.data
}

export const getQuestionsByProject = async (project_id) => {
  const response = await axiosInstance.get(`/api/v1/question/project/${project_id}`)
  return response.data
}

export const sendTweakRequest = async (question_id, session_id, user_message) => {
  const response = await axiosInstance.post(`/api/v1/question/tweak/${question_id}`, {
    session_id: session_id,
    user_message: user_message,
  })
  return response.data
}

export const approveQuestion = async (question_id, session_id) => {
  const response = await axiosInstance.post(`/api/v1/question/approve/${question_id}`, {
    session_id: session_id,
  })
  return response.data
}

export const undoApproval = async (question_id, session_id) => {
  const response = await axiosInstance.post(`/api/v1/question/undoApproval/${question_id}`)
  return response.data
}

export const archiveQuestionById = async (question_id) => {
  const response = await axiosInstance.post(`/api/v1/question/archive/${question_id}`)
  return response.data
}

export const exportQuestions = async (filename, fileformat, questions) => {
  const response = await axiosInstance.post('/api/v1/question/export', {
    filename: filename,
    fileformat: fileformat,
    questions: questions,
  })
  return response.data
}
