<template>
  <component
    :is="elementType"
    :class="classes"
    :aria-disabled="isDisabled || null"
    :type="buttonType"
    :href="isLink ? to : null"
    :tabindex="isDisabled ? -1 : 0"
    v-bind="$attrs"
    @click="handleClick"
  >
    <!-- Icon left -->
    <span
      v-if="icon && iconPosition === 'left'"
      class="mr-2 flex items-center"
    >
      <component :is="icon" class="w-5 h-5" />
    </span>
    <!-- Left icon slot fallback -->
    <span v-if="iconLeft && !icon" class="mr-2 flex items-center">
      <slot name="iconLeft"><i :class="iconLeft" /></slot>
    </span>

    <span v-if="text" class="inline-block">
      <slot>{{ text }}</slot>
    </span>
    <!-- Icon right -->
    <span
      v-if="icon && iconPosition === 'right'"
      class="ml-2 flex items-center"
    >
      <component :is="icon" class="w-5 h-5" />
    </span>
    <!-- Right icon slot fallback -->
    <span v-if="iconRight && !icon" class="ml-2 flex items-center">
      <slot name="iconRight"><i :class="iconRight" /></slot>
    </span>
  </component>
</template>


<script setup>
  import { computed } from 'vue'
  import { Download } from 'lucide-vue-next'

  // Props
  const props = defineProps({
    type: {
      type: String,
      default: 'fill',
      validator: (v) => ['fill', 'ghost', 'flat'].includes(v),
    },
    text: { type: [String, Number], default: '' },
    isDisabled: { type: Boolean, default: false },
    to: { type: String, default: '' }, // For links
    icon: { type: [Object, Function], default: null },
    iconPosition: { type: String, default: 'left', validator: (v) => ['left', 'right'].includes(v) },
    iconLeft: { type: String, default: '' },
    iconRight: { type: String, default: '' },
    size: { type: String, default: 'md', validator: (v) => ['xs', 'sm', 'md', 'lg'].includes(v) },
    shape: { type: String, default: 'rounded', validator: (v) => ['rounded', 'pill'].includes(v) },
    isSubmit: { type: Boolean, default: false },
    active: { type: Boolean, default: false },
  })

  // Computed
  const isLink = computed(() => !!props.to)
  const elementType = computed(() => (isLink.value ? 'a' : 'button'))
  const buttonType = computed(() => (props.isSubmit ? 'submit' : 'button'))

  const classes = computed(() => {
    let base =
      'inline-flex items-center font-semibold focus:outline-none transition-colors select-none'

    // Size
    base += {
      xs: ' text-xs px-2 py-1',
      sm: ' text-sm px-3 py-1',
      md: ' text-base px-4 py-1',
      lg: ' text-lg px-6 py-1',
    }[props.size]

    // Shape
    base += props.shape === 'pill' ? ' rounded-full' : ' rounded-xl'

    // Type (color)
    if (props.type === 'fill') {
      base +=
        ' bg-green-700 text-white hover:bg-green-800 active:bg-green-900 disabled:bg-green-200 disabled:text-gray-400'
      if (props.active) {
        base += ' bg-gray-200 text-black'
      }
    } else if (props.type === 'ghost') {
      base +=
        ' bg-transparent border border-green-700 text-green-700 hover:bg-green-700 hover:text-white active:bg-green-900 active:text-white disabled:border-gray-300 disabled:text-gray-400'
      if (props.active) {
        base += ' bg-gray-200 text-black border-gray-200'
      }
    } else if (props.type === 'flat') {
      base +=
        ' bg-transparent text-green-700 hover:bg-green-100 active:bg-green-200 disabled:text-gray-400'
      if (props.active) {
        base += ' bg-gray-200 text-black'
      }
    }
    if (props.isDisabled) base += ' pointer-events-none opacity-60'
    return base
  })

  // Emits
  const emit = defineEmits(['click'])
  function handleClick(e) {
    if (props.isDisabled) {
      e.preventDefault()
      return
    }
    emit('click', e)
  }
</script>
