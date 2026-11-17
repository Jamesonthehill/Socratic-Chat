import axios from 'axios'

const SERVER_URL = import.meta.env.VITE_SERVER_URL
const backendBaseUrl = SERVER_URL

const axiosInstance = axios.create({
  baseURL: backendBaseUrl,
  headers: {
    'Content-Type': 'application/json',
  },
})

export const initProject = async (project_id) => {
  const response = await axiosInstance.post(`/api/v1/project/init/${project_id}`, {
    project_id: project_id,
  })
  return response.data
} 

export const getProjects = async (user_id) => {
  const response = await axiosInstance.get(`/api/v1/project/user/${user_id}`)
  return response.data
}

export const getSessions = async (user_id, project_id) => {
  const response = await axiosInstance.get(`/api/v1/session/user/${user_id}/project/${project_id}`)
  return response.data
}

export const getSession = async (session_id) => {
  const response = await axiosInstance.get(`/api/v1/session/${session_id}`)
  return response.data
}

export const getSessionMessages = async (session_id) => {
  const response = await axiosInstance.get(`/api/v1/chat/session`, {
    params: {
      session_id: session_id,
    },
  })
  return response.data
}

export const createNewProject = async (name, user_id) => {
  const response = await axiosInstance.post('/api/v1/project/create', {
    name: name,
    user_id: user_id,
  })
  return response.data
}

export const createNewSession = async (user_id, project_id) => {
  const response = await axiosInstance.post('/api/v1/session', {
    user_id: user_id,
    project_id: project_id,
  })
  return response.data
}

export const createInstructions = async (project_id, instructions) => {
  const response = await axiosInstance.put(`/api/v1/project/${project_id}`, {
    instructions: instructions,
  })
  return response.data
}

export const getProject = async (project_id) => {
  const response = await axiosInstance.get(`/api/v1/project/${project_id}`)
  return response.data
}

export const sendMessage = async (user_id, session_id, project_id, user_message) => {
  const response = await axiosInstance.post('/api/v1/chat', {
    user_id: user_id,
    session_id: session_id,
    project_id: project_id,
    role: 'user',
    user_message: user_message,
  })
  return response.data
}

export const createSummary = async (session_id) => {
  const response = await axiosInstance.post('/api/v1/session/summarize', { session_id: session_id })
  return response.data
}

export const createTitle = async (session_id) => {
  if (!session_id) return;
  const data = await getSession(session_id)
  const title = data.session.topic
  if (title === "Untitled" || title === "New Chat") {
    const response = await axiosInstance.post('/api/v1/session/title', { session_id: session_id })
    return response.data
  }
}

export const getQuestions = async (session_id) => {
  const response = await axiosInstance.get(`/api/v1/question/session/${session_id}`, {
    headers: {
      'Content-Type': 'application/json',
    },
  })
  return response.data
}
