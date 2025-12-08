import * as React from "react";
import { cn } from "../../lib/utils";

export interface AlertProps extends React.HTMLAttributes<HTMLDivElement> {
    variant?: "default" | "destructive";
}

const Alert = React.forwardRef<HTMLDivElement, AlertProps>(
    ({ className, variant = "default", ...props }, ref) => (
        <div
            ref={ref}
            role="alert"
            className={cn(
                "relative w-full rounded-lg border p-4",
                {
                    "bg-white text-gray-950 border-gray-200": variant === "default",
                    "border-red-500/50 text-red-600 bg-red-50": variant === "destructive",
                },
                className
            )}
            {...props}
        />
    )
);
Alert.displayName = "Alert";

const AlertDescription = React.forwardRef<
    HTMLParagraphElement,
    React.HTMLAttributes<HTMLParagraphElement>
>(({ className, ...props }, ref) => (
    <div
        ref={ref}
        className={cn("text-sm [&_p]:leading-relaxed", className)}
        {...props}
    />
));
AlertDescription.displayName = "AlertDescription";

export { Alert, AlertDescription };
