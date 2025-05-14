import { useEffect, useState } from 'react';

import { EditablesAPI } from '@/api/api/EditablesAPI';
import { FormGroup } from '@/components/common/FormGroup';
import { useAssetStore } from '@/store/editables/asset/useAssetStore';
import { Material, RenderedMaterial } from '@/types/editables/assetTypes';
import { MarkdownSupported } from '../MarkdownSupported';
import { CodeEditorLabelContent } from './CodeEditorLabelContent';
import { RichTextEditor } from '@/components/common/RichTextEditor';
import { CodeInput } from './CodeInput';
import { TextInput } from './TextInput';
import { useMaterialEditorContent } from './useMaterialEditorContent';

interface MaterialFormProps {
  material: Material;
}

export const MaterialForm = ({ material }: MaterialFormProps) => {
  const setSelectedAsset = useAssetStore((state) => state.setSelectedAsset);
  const handleChange = (value: string) => setSelectedAsset({ ...material, usage: value });
  const [showPreview, setShowPreview] = useState(false);
  const [preview, setPreview] = useState<RenderedMaterial | undefined>(undefined);
  const previewValue = preview ? preview?.content.split('\\n').join('\n') : 'Generating preview...';
  const materialEditorContent = useMaterialEditorContent(material);

  useEffect(() => {
    if (!material) {
      return;
    }

    EditablesAPI.previewMaterial(material).then((preview) => {
      setPreview(preview);
    });
  }, [material]);

  const codePreviewConfig = {
    label: 'Preview of text to be injected into AI context',
    onChange: undefined,
    value: preview?.error ? preview.error : previewValue,
    codeLanguage: 'markdown',
  };

  const editorContent = showPreview ? codePreviewConfig : materialEditorContent;

  const renderEditor = () => {
    if (!editorContent) return null;

    const commonProps = {
      label: editorContent.label,
      value: editorContent.value,
      disabled: showPreview,
    };

    if (material.content_type === 'static_text') {
      return (
        <>
          <div className=" items-center justify-between">
            <label className="text">{editorContent.label}</label>
            <CodeEditorLabelContent showPreview={showPreview} onClick={() => setShowPreview((prev) => !prev)} />
          </div>
          <RichTextEditor
            {...commonProps}
            onChange={(value) => editorContent.onChange?.(value || '')}
            height={400}
            className="w-full flex-grow"
          />
        </>
      );
    }

    return (
      <CodeInput
        {...commonProps}
        labelContent={
          <CodeEditorLabelContent showPreview={showPreview} onClick={() => setShowPreview((prev) => !prev)} />
        }
        labelSize="md"
        onChange={editorContent.onChange}
        codeLanguage={editorContent.codeLanguage}
        readOnly={showPreview}
      />
    );
  };

  return (
    <>
      <FormGroup className="relative w-full">
        <TextInput
          className="min-h-[90px]"
          label="Usage"
          name="usage"
          placeholder="Write text here"
          value={material.usage}
          onChange={handleChange}
          helperText="Usage is used to help identify when this material should be used. "
          resize
        />
        <MarkdownSupported />
      </FormGroup>
      <FormGroup className="w-full flex flex-col">
        <div className="w-full">
          {renderEditor()}
          <MarkdownSupported />
        </div>
      </FormGroup>
    </>
  );
};
