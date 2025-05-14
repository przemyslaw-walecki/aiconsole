import React, { useEffect, useRef } from 'react';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import { Markdown } from 'tiptap-markdown';
import Placeholder from '@tiptap/extension-placeholder';
import Link from '@tiptap/extension-link';
import HorizontalRule from '@tiptap/extension-horizontal-rule';
import { EditorToolbarButton } from '@/components/common/EditorToolbarButton';

interface RichTextEditorProps {
  value: string;
  onChange: (value: string) => void;
  className?: string;
  disabled?: boolean;
  placeholder?: string;
  height?: string | number;
  showPreview?: boolean;
}

export function RichTextEditor({
  value,
  onChange,
  className = '',
  disabled = false,
  placeholder = 'Start typing...',
  height = 400,
  showPreview = false,
}: RichTextEditorProps) {
  const contentRef = useRef<HTMLDivElement>(null);

  const editor = useEditor({
    extensions: [StarterKit, Markdown, Placeholder.configure({ placeholder }), Link, HorizontalRule],
    content: value,
    editable: !disabled && !showPreview,
    onUpdate({ editor }) {
      onChange(editor.storage.markdown.getMarkdown());
    },
  });

  // Sync incoming value changes
  useEffect(() => {
    if (editor && editor.storage.markdown.getMarkdown() !== value) {
      editor.commands.setContent(value, false);
    }
  }, [value, editor]);

  // When entering edit mode, reset selection to start and scroll to top
  useEffect(() => {
    if (!showPreview && editor) {
      editor.chain().focus().setTextSelection({ from: 1, to: 1 }).run();
      // allow ProseMirror to render then reset scroll
      setTimeout(() => {
        if (contentRef.current) {
          contentRef.current.scrollTop = 0;
        }
      }, 0);
    }
  }, [showPreview, editor]);

  const isDisabled = !editor || disabled || showPreview;

  return (
    <div
      className={`${className} w-full flex flex-col bg-gray-800 border border-gray-700 rounded-2xl shadow-lg overflow-hidden`}
      style={{ height: typeof height === 'number' ? `${height}px` : height }}
      data-color-mode="dark"
    >
      {/* Toolbar */}
      <div className="flex flex-wrap gap-2 p-2 bg-gray-700 border-b border-gray-600">
        <EditorToolbarButton
          active={false}
          disabled={isDisabled || !editor?.can().undo()}
          onClick={() => editor?.chain().focus().undo().run()}
        >
          Undo
        </EditorToolbarButton>
        <EditorToolbarButton
          active={false}
          disabled={isDisabled || !editor?.can().redo()}
          onClick={() => editor?.chain().focus().redo().run()}
        >
          Redo
        </EditorToolbarButton>
        <EditorToolbarButton
          active={editor?.isActive('bold') ?? false}
          disabled={isDisabled}
          onClick={() => editor?.chain().focus().toggleBold().run()}
        >
          Bold
        </EditorToolbarButton>
        <EditorToolbarButton
          active={editor?.isActive('italic') ?? false}
          disabled={isDisabled}
          onClick={() => editor?.chain().focus().toggleItalic().run()}
        >
          Italic
        </EditorToolbarButton>
        <EditorToolbarButton
          active={editor?.isActive('strike') ?? false}
          disabled={isDisabled}
          onClick={() => editor?.chain().focus().toggleStrike().run()}
        >
          Strike
        </EditorToolbarButton>
        <EditorToolbarButton
          active={editor?.isActive('code') ?? false}
          disabled={isDisabled}
          onClick={() => editor?.chain().focus().toggleCode().run()}
        >
          Code
        </EditorToolbarButton>
        <EditorToolbarButton
          active={editor?.isActive('codeBlock') ?? false}
          disabled={isDisabled}
          onClick={() => editor?.chain().focus().toggleCodeBlock().run()}
        >
          Code Block
        </EditorToolbarButton>
        <EditorToolbarButton
          active={editor?.isActive('blockquote') ?? false}
          disabled={isDisabled}
          onClick={() => editor?.chain().focus().toggleBlockquote().run()}
        >
          Quote
        </EditorToolbarButton>
        <EditorToolbarButton
          active={editor?.isActive('heading', { level: 1 }) ?? false}
          disabled={isDisabled}
          onClick={() => editor?.chain().focus().toggleHeading({ level: 1 }).run()}
        >
          Header 1
        </EditorToolbarButton>
        <EditorToolbarButton
          active={editor?.isActive('heading', { level: 2 }) ?? false}
          disabled={isDisabled}
          onClick={() => editor?.chain().focus().toggleHeading({ level: 2 }).run()}
        >
          Header 2
        </EditorToolbarButton>
        <EditorToolbarButton
          active={editor?.isActive('heading', { level: 3 }) ?? false}
          disabled={isDisabled}
          onClick={() => editor?.chain().focus().toggleHeading({ level: 3 }).run()}
        >
          Header 3
        </EditorToolbarButton>
        <EditorToolbarButton
          active={editor?.isActive('bulletList') ?? false}
          disabled={isDisabled}
          onClick={() => editor?.chain().focus().toggleBulletList().run()}
        >
          Bullet List
        </EditorToolbarButton>
        <EditorToolbarButton
          active={editor?.isActive('orderedList') ?? false}
          disabled={isDisabled}
          onClick={() => editor?.chain().focus().toggleOrderedList().run()}
        >
          Numbered List
        </EditorToolbarButton>
        <EditorToolbarButton
          active={false}
          disabled={isDisabled}
          onClick={() => editor?.chain().focus().setHorizontalRule().run()}
        >
          Horizontal Rule
        </EditorToolbarButton>
        <EditorToolbarButton
          active={editor?.isActive('link') ?? false}
          disabled={isDisabled}
          onClick={() => {
            const url = window.prompt('Enter link URL');
            if (url) {
              editor?.chain().focus().extendMarkRange('link').setLink({ href: url }).run();
            }
          }}
        >
          Link
        </EditorToolbarButton>
      </div>

      {/* Content Area */}
      <div
        ref={contentRef}
        className={`w-full flex-1 overflow-auto p-4 prose prose-invert max-w-none ${
          showPreview ? 'bg-gray-900 text-gray-100' : ''
        }`}
      >
        <EditorContent editor={editor!} />
      </div>
    </div>
  );
}
