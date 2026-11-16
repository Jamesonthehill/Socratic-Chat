import axios from 'axios'

let backendBaseUrl = ''

if (import.meta.env.MODE === 'development') {
  backendBaseUrl = import.meta.env.VITE_LIGHTRAG_SERVER || ''
} else {
  backendBaseUrl = '/ml'
}

// Axios instance
const axiosInstance = axios.create({
  baseURL: backendBaseUrl,
  headers: {
    'Content-Type': 'application/json',
  },
})

// API methods
export const queryGraphs = async (label, maxDepth, maxNodes) => {
  const response = await axiosInstance.get(
    `/graphs?label=${encodeURIComponent(label)}&max_depth=${maxDepth}&max_nodes=${maxNodes}`
  )
  return response.data
}

export const getGraphLabels = async () => {
  const response = await axiosInstance.get('/graph/label/list')
  return response.data
}

export const checkHealth = async () => {
    const response = await axiosInstance.get('/health')
    return response.data
}

export const getDocuments = async () => {
  const response = await axiosInstance.get('/documents')
  return response.data
}

export const scanNewDocuments = async () => {
  const response = await axiosInstance.post('/documents/scan')
  return response.data
}

export const getDocumentsScanProgress = async () => {
  const response = await axiosInstance.get('/documents/scan-progress')
  return response.data
}

export const queryText = async (request) => {
  const response = await axiosInstance.post('/query', request)
  return response.data
}

export const queryTextStream = async (request, onChunk, onError) => {
  const headers = {
    'Content-Type': 'application/json',
    Accept: 'application/x-ndjson',
  }

  try {
    const response = await fetch(`/query/stream`, {
      method: 'POST',
      headers: headers,
      body: JSON.stringify(request),
    })

    if (!response.ok) {
      // Handle 401 Unauthorized error specifically
      if (response.status === 401) {
        // Create a specific authentication error
        const authError = new Error('Authentication required')
        throw authError
      }

      // Handle other common HTTP errors with specific messages
      let errorBody = 'Unknown error'
      try {
        errorBody = await response.text() // Try to get error details from body
      } catch {
        /* ignore */
      }

      // Format error message similar to axiosInstance interceptor for consistency
      const url = `/query/stream`
      throw new Error(
        `${response.status} ${response.statusText}\n${JSON.stringify({ error: errorBody })}\n${url}`
      )
    }

    if (!response.body) {
      throw new Error('Response body is null')
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) {
        break // Stream finished
      }

      // Decode the chunk and add to buffer
      buffer += decoder.decode(value, { stream: true }) // stream: true handles multi-byte chars split across chunks

      // Process complete lines (NDJSON)
      const lines = buffer.split('\n')
      buffer = lines.pop() || '' // Keep potentially incomplete line in buffer

      for (const line of lines) {
        if (line.trim()) {
          try {
            const parsed = JSON.parse(line)
            if (parsed.response) {
              onChunk(parsed.response)
            } else if (parsed.error && onError) {
              onError(parsed.error)
            }
          } catch (error) {
            console.error('Error parsing stream chunk:', line, error)
            if (onError) onError(`Error parsing server response: ${line}`)
          }
        }
      }
    }

    // Process any remaining data in the buffer after the stream ends
    if (buffer.trim()) {
      try {
        const parsed = JSON.parse(buffer)
        if (parsed.response) {
          onChunk(parsed.response)
        } else if (parsed.error && onError) {
          onError(parsed.error)
        }
      } catch (error) {
        console.error('Error parsing final chunk:', buffer, error)
        if (onError) onError(`Error parsing final server response: ${buffer}`)
      }
    }
  } catch (error) {
    const message = error

    // Check if this is an authentication error
    if (message === 'Authentication required') {
      // Already navigated to login page in the response.status === 401 block
      console.error('Authentication required for stream request')
      if (onError) {
        onError('Authentication required')
      }
      return // Exit early, no need for further error handling
    }

    // Check for specific HTTP error status codes in the error message
    const statusCodeMatch = message.match(/^(\d{3})\s/)
    if (statusCodeMatch) {
      const statusCode = parseInt(statusCodeMatch[1], 10)

      // Handle specific status codes with user-friendly messages
      let userMessage = message

      switch (statusCode) {
        case 403:
          userMessage = 'You do not have permission to access this resource (403 Forbidden)'
          console.error('Permission denied for stream request:', message)
          break
        case 404:
          userMessage = 'The requested resource does not exist (404 Not Found)'
          console.error('Resource not found for stream request:', message)
          break
        case 429:
          userMessage = 'Too many requests, please try again later (429 Too Many Requests)'
          console.error('Rate limited for stream request:', message)
          break
        case 500:
        case 502:
        case 503:
        case 504:
          userMessage = `Server error, please try again later (${statusCode})`
          console.error('Server error for stream request:', message)
          break
        default:
          console.error('Stream request failed with status code:', statusCode, message)
      }

      if (onError) {
        onError(userMessage)
      }
      return
    }

    // Handle network errors (like connection refused, timeout, etc.)
    if (
      message.includes('NetworkError') ||
      message.includes('Failed to fetch') ||
      message.includes('Network request failed')
    ) {
      console.error('Network error for stream request:', message)
      if (onError) {
        onError('Network connection error, please check your internet connection')
      }
      return
    }

    // Handle JSON parsing errors during stream processing
    if (message.includes('Error parsing') || message.includes('SyntaxError')) {
      console.error('JSON parsing error in stream:', message)
      if (onError) {
        onError('Error processing response data')
      }
      return
    }

    // Handle other errors
    console.error('Unhandled stream error:', message)
    if (onError) {
      onError(message)
    } else {
      console.error('No error handler provided for stream error:', message)
    }
  }
}

export const insertText = async (text) => {
  const response = await axiosInstance.post('/documents/text', { text })
  return response.data
}

export const insertTexts = async (texts) => {
  const response = await axiosInstance.post('/documents/texts', { texts })
  return response.data
}

export const insertLinks = async (links) => {
  const response = await axiosInstance.post('/documents/links', { links })
  return response.data
}

export const uploadDocument = async (file, onUploadProgress) => {
  const formData = new FormData()
  formData.append('file', file)

  const response = await axiosInstance.post('/documents/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    onUploadProgress:
      typeof onUploadProgress === 'function'
        ? (progressEvent) => {
            const total = progressEvent.total || 1
            const percentCompleted = Math.round((progressEvent.loaded * 100) / total)
            onUploadProgress(percentCompleted)
          }
        : undefined,
  })

  return response.data
}

export const batchUploadDocuments = async (files, onUploadProgress) => {
  return await Promise.all(
    files.map(async (file) => {
      return await uploadDocument(file, (percentCompleted) => {
        onUploadProgress?.(file.name, percentCompleted)
      })
    })
  )
}

export const clearDocuments = async () => {
  const response = await axiosInstance.delete('/documents')
  return response.data
}

export const clearCache = async (modes) => {
  const response = await axiosInstance.post('/documents/clear_cache', { modes })
  return response.data
}

export const getPipelineStatus = async () => {
  const response = await axiosInstance.get('/documents/pipeline_status')
  return response.data
}

export const loginToServer = async (username, password) => {
  const formData = new FormData()
  formData.append('username', username)
  formData.append('password', password)

  const response = await axiosInstance.post('/login', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })

  return response.data
}

/**
 * Updates an entity's properties in the knowledge graph
 * @param entityName The name of the entity to update
 * @param updatedData Dictionary containing updated attributes
 * @param allowRename Whether to allow renaming the entity (default: false)
 * @returns Promise with the updated entity information
 */
export const updateEntity = async (entityName, updatedData, allowRename = false) => {
  const response = await axiosInstance.post('/graph/entity/edit', {
    entity_name: entityName,
    updated_data: updatedData,
    allow_rename: allowRename,
  })
  return response.data
}

/**
 * Updates a relation's properties in the knowledge graph
 * @param sourceEntity The source entity name
 * @param targetEntity The target entity name
 * @param updatedData Dictionary containing updated attributes
 * @returns Promise with the updated relation information
 */
export const updateRelation = async (sourceEntity, targetEntity, updatedData) => {
  const response = await axiosInstance.post('/graph/relation/edit', {
    source_id: sourceEntity,
    target_id: targetEntity,
    updated_data: updatedData,
  })
  return response.data
}

/**
 * Checks if an entity name already exists in the knowledge graph
 * @param entityName The entity name to check
 * @returns Promise with boolean indicating if the entity exists
 */
export const checkEntityNameExists = async (entityName) => {
  try {
    const response = await axiosInstance.get(
      `/graph/entity/exists?name=${encodeURIComponent(entityName)}`
    )
    return response.data.exists
  } catch (error) {
    console.error('Error checking entity name:', error)
    return false
  }
}
