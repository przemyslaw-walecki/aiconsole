import React from 'react';
import clsx from 'clsx';

interface EditorToolbarButtonProps {
  active: boolean;
  disabled?: boolean;
  onClick: () => void;
  children: React.ReactNode;
}

export function EditorToolbarButton({ active, disabled = false, onClick, children }: EditorToolbarButtonProps) {
  const base = 'px-3 py-1 border rounded text-sm font-medium focus:outline-none focus:ring-2 focus:ring-offset-1';
  const activeCls = 'bg-gray-600 text-white border-gray-400';
  const inactiveCls = 'text-gray-300 border-gray-600 hover:bg-gray-600 hover:border-gray-500';

  return (
    <button disabled={disabled} onClick={onClick} className={clsx(base, active ? activeCls : inactiveCls)}>
      {children}
    </button>
  );
}
